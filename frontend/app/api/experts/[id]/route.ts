import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/experts/${id}`), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json();
  const res = await fetch(backendUrl(`/api/experts/${id}`), {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/experts/${id}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
