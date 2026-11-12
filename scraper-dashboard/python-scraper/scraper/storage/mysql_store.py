import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

import pymysql
from scraper.fetching.http_client import check_url_alive, is_github_issue_open
from scraper.models.job import NormalizedJob
from scraper.validation.job_validator import _extract_apply_url_from_description

CONFIRMED_DEAD_PREFIXES = (
    "soft_404_",
    "github_issue_closed",
    "dead_link_404",
    "dead_link_410",
)

REQUIRED_COLUMNS: dict[str, str] = {
    "source": "VARCHAR(50) NOT NULL DEFAULT 'unknown'",
    "source_url": "TEXT NULL",
    "apply_url": "TEXT NULL",
    "external_id": "VARCHAR(100) NULL",
    "title": "VARCHAR(255) NOT NULL DEFAULT ''",
    "company": "VARCHAR(255) NULL",
    "description": "LONGTEXT NULL",
    "work_mode": "VARCHAR(50) NULL",
    "seniority": "VARCHAR(50) NULL",
    "employment_type": "VARCHAR(50) NULL",
    "city": "VARCHAR(100) NULL",
    "state": "VARCHAR(100) NULL",
    "published_at": "DATETIME NULL",
    "fetched_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "content_hash": "VARCHAR(64) NULL",
}


def get_db_connection():
    host = os.getenv("DB_HOST", "127.0.0.1")
    if host.lower() == "localhost":
        host = "127.0.0.1"

    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "vagas_nordestinas")

    ssl_config = None
    if "aivencloud.com" in host or os.getenv("DB_USE_SSL", "").lower() == "true":
        ssl_config = {"ssl": True}

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        ssl=ssl_config,
        autocommit=True,
        connect_timeout=10,
    )


def _ensure_schema(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source VARCHAR(50) NOT NULL,
            source_url TEXT NOT NULL,
            apply_url TEXT NULL,
            external_id VARCHAR(100) NULL,
            title VARCHAR(255) NOT NULL,
            company VARCHAR(255) NULL,
            description LONGTEXT NULL,
            work_mode VARCHAR(50) NULL,
            seniority VARCHAR(50) NULL,
            employment_type VARCHAR(50) NULL,
            city VARCHAR(100) NULL,
            state VARCHAR(100) NULL,
            published_at DATETIME NULL,
            fetched_at DATETIME NOT NULL,
            content_hash VARCHAR(64) UNIQUE NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("SHOW COLUMNS FROM jobs")
    existing_columns = {row[0] for row in cursor.fetchall()}

    for col_name, col_definition in REQUIRED_COLUMNS.items():
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_definition}")

    # Se a tabela antiga usava 'url' como NOT NULL, migra os dados e libera NULL para não travar o INSERT
    if "url" in existing_columns:
        cursor.execute("UPDATE jobs SET source_url = url WHERE source_url IS NULL OR source_url = ''")
        cursor.execute("ALTER TABLE jobs MODIFY COLUMN url TEXT NULL")

    # Garante índice único em content_hash para o ON DUPLICATE KEY UPDATE funcionar
    cursor.execute("SHOW INDEX FROM jobs WHERE Column_name = 'content_hash' AND Non_unique = 0")
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE jobs ADD UNIQUE INDEX idx_jobs_content_hash (content_hash)")


def persist_jobs_to_mysql(jobs: list[NormalizedJob]) -> None:
    if not jobs:
        print("Nenhuma vaga válida para inserir no MySQL.")
        return

    print("🔄 Tentando conectar ao MySQL...")
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            _ensure_schema(cursor)

            sql = """
                INSERT INTO jobs (
                    source, source_url, apply_url, external_id, title, company,
                    description, work_mode, seniority, employment_type,
                    city, state, published_at, fetched_at, content_hash
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON DUPLICATE KEY UPDATE
                    apply_url = VALUES(apply_url),
                    title = VALUES(title),
                    company = VALUES(company),
                    description = VALUES(description),
                    work_mode = VALUES(work_mode),
                    seniority = VALUES(seniority),
                    employment_type = VALUES(employment_type),
                    city = VALUES(city),
                    state = VALUES(state),
                    fetched_at = VALUES(fetched_at);
            """

            records = [
                (
                    job.source,
                    str(job.source_url),
                    job.apply_url,
                    job.external_id,
                    job.title,
                    job.company,
                    job.description,
                    job.work_mode.value if job.work_mode else None,
                    job.seniority.value if job.seniority else None,
                    job.employment_type.value if job.employment_type else None,
                    job.city,
                    job.state,
                    job.published_at,
                    job.fetched_at,
                    job.content_hash,
                )
                for job in jobs
            ]

            cursor.executemany(sql, records)
            print(f"✅ {len(records)} vagas sincronizadas com sucesso no MySQL!")

        connection.close()
    except Exception as err:
        print(f"❌ Erro ao conectar/salvar no MySQL: {err}")


def _check_stored_row(row: tuple) -> tuple[int, str, str]:
    """Retorna (id, title, motivo_remocao) se a vaga salva no banco estiver morta."""
    job_id, title, source_url, apply_url, description = row
    parts = urlsplit(source_url or "")
    is_github_issue = parts.hostname == "github.com" and "/issues/" in parts.path

    if is_github_issue:
        if not is_github_issue_open(source_url):
            return job_id, title, "github_issue_closed"
    elif source_url:
        alive, reason = check_url_alive(source_url)
        if not alive and reason.startswith(CONFIRMED_DEAD_PREFIXES):
            return job_id, title, reason

    target_apply = apply_url
    if not target_apply and is_github_issue and description:
        target_apply = _extract_apply_url_from_description(description)

    if target_apply and target_apply != source_url:
        alive, reason = check_url_alive(target_apply)
        if not alive and reason.startswith(CONFIRMED_DEAD_PREFIXES):
            return job_id, title, f"apply_{reason}"

    return job_id, title, ""


def cleanup_dead_jobs(max_workers: int = 10) -> None:
    """Revalida vagas já existentes no MySQL e remove as que expiraram ou viraram 404."""
    print("🧹 Verificando vagas antigas no MySQL para limpeza...")
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            _ensure_schema(cursor)
            cursor.execute("SELECT id, title, source_url, apply_url, description FROM jobs")
            rows = cursor.fetchall()

            if not rows:
                print("Nenhuma vaga no banco para revalidar.")
                return

            dead_ids: list[int] = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_check_stored_row, row) for row in rows]
                for future in as_completed(futures):
                    job_id, title, reason = future.result()
                    if reason:
                        dead_ids.append(job_id)
                        print(f"🗑️ Removendo vaga expirada [{job_id}] '{title}': {reason}")

            if dead_ids:
                placeholders = ", ".join(["%s"] * len(dead_ids))
                cursor.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", dead_ids)
                print(f"✅ Limpeza concluída: {len(dead_ids)} vagas mortas removidas.")
            else:
                print("✅ Limpeza concluída: nenhuma vaga expirada encontrada no banco.")

        connection.close()
    except Exception as err:
        print(f"❌ Erro durante a limpeza de vagas no MySQL: {err}")