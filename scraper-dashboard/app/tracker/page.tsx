"use client";

import { useCallback, useEffect, useState } from "react";

interface Job {
  id: number;
  title: string;
  company: string | null;
  source: string;
  source_url: string | null;
  apply_url: string | null;
  work_mode: string | null;
  city: string | null;
  state: string | null;
}

async function requestJobs(): Promise<Job[]> {
  const response = await fetch("/api/jobs", { cache: "no-store" });
  const payload = (await response.json()) as {
    jobs?: Job[];
    error?: string;
  };

  if (!response.ok) {
    throw new Error(payload.error || "Não foi possível carregar as vagas.");
  }
  if (!Array.isArray(payload.jobs)) {
    throw new Error("A resposta do banco não contém uma lista de vagas.");
  }

  return payload.jobs;
}

export default function Tracker() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      setJobs(await requestJobs());
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Não foi possível carregar as vagas."
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    requestJobs()
      .then((loadedJobs) => {
        if (active) setJobs(loadedJobs);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Não foi possível carregar as vagas."
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#FFF5EA] p-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-extrabold text-[#EA7805]">
              Vagas no MySQL
            </h1>
            <p className="mt-2 text-[#7E4220]">
              Lista atualizada diretamente do banco de dados.
            </p>
          </div>
          <button
            onClick={() => void loadJobs()}
            disabled={isLoading}
            className="rounded-full bg-[#EA7805] px-6 py-2 font-bold text-white shadow-md transition-colors hover:bg-[#7E4220] disabled:opacity-50"
          >
            {isLoading ? "Carregando..." : "Atualizar lista"}
          </button>
        </div>

        <section className="rounded-xl border border-[#F1B435] bg-white p-6 shadow-lg">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-xl font-bold text-[#191815]">
              Vagas disponíveis
            </h2>
            <span className="rounded-full bg-[#F1B435] px-3 py-1 text-sm font-bold text-[#191815]">
              {jobs.length}
            </span>
          </div>

          {error ? (
            <p role="alert" className="text-red-700">
              {error}
            </p>
          ) : isLoading ? (
            <p className="text-[#7E4220]">Carregando vagas do MySQL...</p>
          ) : jobs.length === 0 ? (
            <p className="text-[#7E4220]">Nenhuma vaga encontrada no MySQL.</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {jobs.map((job) => {
                const url = job.apply_url;

                return (
                  <article
                    key={job.id}
                    className="rounded-lg border-l-4 border-[#EA7805] bg-[#FFF5EA] p-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-bold text-[#191815]">{job.title}</h3>
                      {job.work_mode && (
                        <span className="shrink-0 rounded-full bg-[#F1B435] px-2 py-1 text-xs text-[#191815]">
                          {job.work_mode}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-[#7E4220]">
                      {job.company || "Empresa não informada"}
                    </p>
                    <p className="mt-1 text-sm text-[#7E4220]">
                      {[job.city, job.state].filter(Boolean).join(", ") ||
                        "Local não informado"}
                      {" · "}
                      {job.source}
                    </p>
                    {url && (
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 inline-block font-semibold text-[#EA7805] hover:underline"
                      >
                        Ver vaga
                      </a>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
