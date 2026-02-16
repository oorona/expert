import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const clientKey = request.headers.get("X-Client-Key") || "";
  const res = await fetch(backendUrl("/api/v1/ingest/experts"), {
    headers: {
      ...authHeaders(),
      "X-Client-Key": clientKey,
    },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
