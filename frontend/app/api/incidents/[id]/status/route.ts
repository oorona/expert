import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  const res = await fetch(backendUrl(`/api/incidents/${id}/status`), {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
