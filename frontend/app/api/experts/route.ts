import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET() {
  const res = await fetch(backendUrl("/api/experts"), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const res = await fetch(backendUrl("/api/experts"), {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });

  // Stream SSE through to the client
  if (res.headers.get("content-type")?.includes("text/event-stream")) {
    return new Response(res.body, {
      status: res.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  // Fallback: return JSON as before
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
