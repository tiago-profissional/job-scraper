try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper.storage.mysql_store import _ensure_schema, get_db_connection


def reset_jobs_table() -> None:
    print("⚠️ Conectando ao MySQL para resetar APENAS a tabela 'jobs'...")
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            print(f"📦 Banco conectado: {db_name}")

            cursor.execute("DROP TABLE IF EXISTS jobs;")
            print("🗑️ Tabela 'jobs' removida.")

            _ensure_schema(cursor)
            print("✅ Tabela 'jobs' recriada com o schema atualizado!")
    finally:
        connection.close()


if __name__ == "__main__":
    reset_jobs_table()