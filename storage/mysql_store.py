import os
import pymysql
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def persist_jobs_to_mysql(jobs: list) -> None:
    if not jobs:
        print("Nenhuma vaga para guardar no MySQL.")
        return
        
    try:
        connection = pymysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "vagas_nordestinas")
        )
        
        added = 0
        with connection.cursor() as cursor:
            for job in jobs:
                # Verifica se a vaga já existe pelo título e empresa para não duplicar
                cursor.execute(
                    "SELECT id FROM jobs WHERE title = %s AND company = %s",
                    (job.title, job.company)
                )
                
                if not cursor.fetchone():
                    # Insere mapeando para as colunas exatas da sua tabela do phpMyAdmin
                    sql = """
                        INSERT INTO jobs (
                            title, company, description, status, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(sql, (
                        job.title, 
                        job.company, 
                        job.description, 
                        "Rascunho", # O mesmo status que as suas vagas de teste têm
                        now, 
                        now
                    ))
                    added += 1
                    
        connection.commit()
        print(f"✅ Sucesso: {added} novas vagas inseridas na base de dados 'vagas_nordestinas'.")
    except Exception as e:
        print(f"❌ Erro ao ligar ao MySQL: {e}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()