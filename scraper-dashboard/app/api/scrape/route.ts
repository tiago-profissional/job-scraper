import { createHash } from 'node:crypto';
import { scrapeStartupJobs } from '@/lib/scraper';
import pool from '@/lib/db';

export async function GET() {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const sendLog = (message: string, type: 'info' | 'success' | 'error' = 'info') => {
        const data = JSON.stringify({ type, message, timestamp: new Date().toISOString() });
        controller.enqueue(encoder.encode(`data: ${data}\n\n`));
      };

      try {
        sendLog('🚀 Iniciando scraper de Startups...', 'info');
        
        const jobs = await scrapeStartupJobs();
        if (jobs.length === 0) {
          sendLog('⚠️ Nenhuma vaga encontrada.', 'error');
          controller.close();
          return;
        }

        sendLog(`📦 Encontradas ${jobs.length} vagas. Salvando...`, 'success');

        await pool.query('SELECT 1 AS connected');
        sendLog('🔗 Conectado ao MySQL.', 'success');

        let savedCount = 0;
        for (const job of jobs) {
          sendLog(`📝 Processando: ${job.title} (${job.company})`, 'info');
          try {
            const contentHash = createHash('sha256')
              .update(job.source_url)
              .digest('hex');
            await pool.execute(
              `INSERT INTO jobs (
                 source, source_url, apply_url, title, company, description,
                 work_mode, seniority, employment_type, city, state,
                 published_at, fetched_at, content_hash
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
               ON DUPLICATE KEY UPDATE
                 apply_url = VALUES(apply_url),
                 title = VALUES(title),
                 company = VALUES(company),
                 description = VALUES(description),
                 work_mode = VALUES(work_mode),
                 seniority = VALUES(seniority),
                 employment_type = VALUES(employment_type),
                 city = VALUES(city),
                 state = VALUES(state),
                 published_at = VALUES(published_at),
                 fetched_at = CURRENT_TIMESTAMP`,
              [
                job.source,
                job.source_url,
                job.apply_url,
                job.title,
                job.company,
                job.description,
                job.work_mode,
                job.seniority,
                job.employment_type,
                job.city,
                job.state,
                job.published_at,
                contentHash,
              ]
            );
            savedCount++;
            sendLog(`✅ ${job.title} salvo com sucesso! (${savedCount}/${jobs.length})`, 'success');
          } catch (err: unknown) {
            const message = err instanceof Error ? err.message : String(err);
            sendLog(`❌ Erro ao salvar ${job.title}: ${message}`, 'error');
          }
        }

        sendLog(`🎉 Finalizado! ${savedCount} vagas salvas.`, 'success');
        controller.close();
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        sendLog(`💥 Erro crítico: ${message}`, 'error');
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}