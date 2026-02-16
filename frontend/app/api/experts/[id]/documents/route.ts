import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/experts/${id}/documents`), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const formData = await request.formData();
  const res = await fetch(backendUrl(`/api/experts/${id}/documents`), {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
