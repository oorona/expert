import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const clientKey = request.headers.get("X-Client-Key") || "";

  const res = await fetch(backendUrl("/api/v1/ingest"), {
    method: "POST",
    headers: {
      ...authHeaders({ "Content-Type": "application/json" }),
      "X-Client-Key": clientKey,
    },
    body,
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
