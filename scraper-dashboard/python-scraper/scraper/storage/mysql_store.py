import os
import pymysql
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def persist_jobs_to_mysql(jobs: list) -> None:
    if not jobs:
        print("Nenhuma vaga para guardar no MySQL.")
        return
        
    host = os.getenv("DB_HOST", "127.0.0.1").strip()
    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER", "root").strip()
    password = os.getenv("DB_PASSWORD", "").strip()
    db_name = os.getenv("DB_NAME", "vagas_nordestinas").strip()
    
    print(f"🔄 A tentar ligar ao MySQL na porta {port} (BD: {db_name})...")
    
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db_name,
            connect_timeout=15,
            ssl={'ca': '/etc/ssl/certs/ca-certificates.crt'} 
        )
        
        added = 0
        with connection.cursor() as cursor:
            for job in jobs:
                cursor.execute(
                    "SELECT id FROM jobs WHERE title = %s AND company = %s",
                    (job.title, job.company)
                )
                if not cursor.fetchone():
                    sql = """
                        INSERT INTO jobs (
                            title, company, description, status, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(sql, (
                        job.title, job.company, job.description, "Rascunho", now, now
                    ))
                    added += 1
                    
        connection.commit()
        print(f"✅ Sucesso: {added} novas vagas inseridas na base de dados.")
    except Exception as e:
        print(f"❌ Erro ao ligar ao MySQL: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()