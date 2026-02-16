import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const res = await fetch(backendUrl("/api/incidents/link"), {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
