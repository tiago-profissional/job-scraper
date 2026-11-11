import os
import pymysql

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "vagas_nordestinas")

try:
    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=True
    )
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE jobs;")
        print("✅ Tabela 'jobs' zerada com sucesso!")
except Exception as e:
    print(f"❌ Erro ao conectar/zerar o banco: {e}")
finally:
    if 'connection' in locals() and connection.open:
        connection.close()