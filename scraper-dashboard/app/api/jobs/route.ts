import { NextResponse } from "next/server";

import { getJobs } from "@/lib/jobs";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const jobs = await getJobs();
    return NextResponse.json({ jobs });
  } catch (error) {
    console.error("Failed to load jobs from MySQL:", error);
    return NextResponse.json(
      { error: "Não foi possível carregar as vagas do MySQL." },
      { status: 500 }
    );
  }
}
