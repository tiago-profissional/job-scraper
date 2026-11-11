import os
import pymysql
from scraper.models.job import NormalizedJob

def get_db_connection():
    host = os.getenv("DB_HOST", "127.0.0.1")
    # Substitui 'localhost' para evitar o erro 'No such file or directory' no Linux/GitHub Actions
    if host.lower() == "localhost":
        host = "127.0.0.1"

    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "vagas_nordestinas")

    # Configuração de SSL para bancos em nuvem (ex: Aiven)
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
        connect_timeout=10
    )


def persist_jobs_to_mysql(jobs: list[NormalizedJob]) -> None:
    if not jobs:
        print("Nenhuma vaga válida para inserir no MySQL.")
        return

    print(f"🔄 Tentando conectar ao MySQL...")
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Cria a tabela caso ainda não exista
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

            records = []
            for job in jobs:
                records.append((
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
                    job.content_hash
                ))

            cursor.executemany(sql, records)
            print(f"✅ {len(records)} vagas sincronizadas com sucesso no MySQL!")

        connection.close()
    except Exception as err:
        print(f"❌ Erro ao conectar/salvar no MySQL: {err}")