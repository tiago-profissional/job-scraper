import { getJobs } from "@/lib/jobs";

export const dynamic = "force-dynamic";

function formatDate(value: Date | string | null) {
  if (!value) return "Data não informada";

  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime())
    ? "Data não informada"
    : date.toLocaleString("pt-BR");
}

export default async function Dashboard() {
  const jobs = await getJobs();
  const recentJobs = jobs.slice(0, 20);
  const remoteJobs = jobs.filter((job) =>
    job.work_mode?.toLowerCase().includes("remot")
  ).length;

  return (
    <div className="min-h-screen bg-[#FFF5EA] p-8">
      <div className="mx-auto mb-8 max-w-7xl">
        <h1 className="text-3xl font-extrabold text-[#EA7805]">
          Vagas cadastradas
        </h1>
        <p className="mt-2 text-[#7E4220]">
          Dados carregados exclusivamente do banco MySQL.
        </p>
      </div>

      <div className="mx-auto mb-8 grid max-w-7xl grid-cols-1 gap-6 md:grid-cols-2">
        <section className="rounded-xl border-l-4 border-[#F1B435] bg-white p-6 shadow-lg">
          <h2 className="text-lg font-semibold text-[#191815]">Total de vagas</h2>
          <p className="mt-2 text-3xl font-extrabold text-[#EA7805]">
            {jobs.length}
          </p>
        </section>
        <section className="rounded-xl border-l-4 border-[#EA7805] bg-white p-6 shadow-lg">
          <h2 className="text-lg font-semibold text-[#191815]">Vagas remotas</h2>
          <p className="mt-2 text-3xl font-extrabold text-[#F1B435]">
            {remoteJobs}
          </p>
        </section>
      </div>

      <section className="mx-auto max-w-7xl rounded-xl border border-[#F1B435] bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-xl font-bold text-[#EA7805]">
          Vagas mais recentes
        </h2>
        {recentJobs.length === 0 ? (
          <p className="text-[#7E4220]">Nenhuma vaga encontrada no MySQL.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-[#7E4220] text-[#FFF5EA]">
                  <th className="rounded-l-lg p-3">Título</th>
                  <th className="p-3">Empresa</th>
                  <th className="p-3">Local</th>
                  <th className="p-3">Fonte</th>
                  <th className="rounded-r-lg p-3">Publicação</th>
                </tr>
              </thead>
              <tbody>
                {recentJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-[#FFF5EA] hover:bg-[#FFF5EA]"
                  >
                    <td className="p-3 font-semibold text-[#191815]">
                      {job.apply_url ? (
                        <a
                          href={job.apply_url}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:text-[#EA7805]"
                        >
                          {job.title}
                        </a>
                      ) : (
                        job.title
                      )}
                    </td>
                    <td className="p-3 text-[#191815]">
                      {job.company || "Empresa não informada"}
                    </td>
                    <td className="p-3 text-[#7E4220]">
                      {[job.city, job.state].filter(Boolean).join(", ") ||
                        job.work_mode ||
                        "Local não informado"}
                    </td>
                    <td className="p-3 text-[#7E4220]">{job.source}</td>
                    <td className="p-3 text-[#7E4220]">
                      {formatDate(job.published_at || job.fetched_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
