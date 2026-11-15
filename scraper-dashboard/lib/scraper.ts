export interface JobData {
  source: string;
  source_url: string;
  apply_url: string | null;
  title: string;
  company: string;
  description: string | null;
  work_mode: string | null;
  seniority: string | null;
  employment_type: string | null;
  city: string | null;
  state: string | null;
  published_at: string | null;
}

export async function scrapeStartupJobs(): Promise<JobData[]> {
  // 🔹 Opção 1: DADOS MOCKADOS (para testar a interface agora)
  // Depois você substitui pela raspagem real.
  
  // Simula um delay para parecer que está buscando dados
  await new Promise(resolve => setTimeout(resolve, 1500));

  return [
    {
      source: 'startup',
      source_url: 'https://starkbank.com/careers',
      apply_url: null,
      title: 'Engenheiro de Software Sênior',
      company: 'Stark Bank',
      description: 'Node.js, React, AWS',
      work_mode: null,
      seniority: 'senior',
      employment_type: null,
      city: 'São Paulo',
      state: 'SP',
      published_at: null
    },
    {
      source: 'startup',
      source_url: 'https://brex.com/jobs',
      apply_url: null,
      title: 'Product Designer',
      company: 'Brex',
      description: 'Figma, UI/UX',
      work_mode: 'remote',
      seniority: null,
      employment_type: null,
      city: null,
      state: null,
      published_at: null
    },
    {
      source: 'startup',
      source_url: 'https://vercel.com/jobs',
      apply_url: null,
      title: 'Backend Engineer',
      company: 'Vercel',
      description: 'Rust, Go',
      work_mode: null,
      seniority: null,
      employment_type: null,
      city: 'São Francisco',
      state: 'CA',
      published_at: null
    }
  ];

  // 🔹 Opção 2: RASPAGEM REAL (quando você tiver os seletores certos)
  /*
  const url = 'https://www.workatastartup.com/jobs';
  const response = await axios.get(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 ...' }
  });
  const $ = cheerio.load(response.data);
  const jobs: JobData[] = [];
  
  $('div.job-card').each((_, el) => {
    const title = $(el).find('a.job-title').text().trim();
    const company = $(el).find('div.company-name').text().trim();
    // ... preencher os campos e adicionar ao array
  });
  return jobs;
  */
}