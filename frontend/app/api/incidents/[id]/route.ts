import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/incidents/${id}`), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/incidents/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
    cache: "no-store",
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  const res = await fetch(backendUrl(`/api/incidents/${id}`), {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
