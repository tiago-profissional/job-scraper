import type { RowDataPacket } from "mysql2";

import pool from "@/lib/db";

export interface JobRecord extends RowDataPacket {
  id: number;
  source: string;
  source_url: string | null;
  apply_url: string | null;
  title: string;
  company: string | null;
  description: string | null;
  work_mode: string | null;
  seniority: string | null;
  employment_type: string | null;
  city: string | null;
  state: string | null;
  published_at: Date | string | null;
  fetched_at: Date | string | null;
}

export async function getJobs(): Promise<JobRecord[]> {
  const [rows] = await pool.query<JobRecord[]>(`
    SELECT
      id, source, source_url, apply_url, title, company, description,
      work_mode, seniority, employment_type, city, state, published_at,
      fetched_at
    FROM jobs
    ORDER BY COALESCE(published_at, fetched_at) DESC, id DESC
  `);

  return rows;
}
