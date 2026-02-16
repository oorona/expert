import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const res = await fetch(backendUrl("/api/diagnose"), {
    method: "POST",
    headers: authHeaders(),
    body: formData,
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

  const data = await res.json();
  return Response.json(data, { status: res.status });
}
