import { NextRequest, NextResponse } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/experts/${id}/store-documents`), {
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
  const { document_name } = await request.json();
  const res = await fetch(
    backendUrl(`/api/experts/${id}/store-documents/${encodeURIComponent(document_name)}`),
    { method: "DELETE", headers: authHeaders() }
  );
  if (!res.ok) {
    return NextResponse.json(
      { error: await res.text() },
      { status: res.status }
    );
  }
  return NextResponse.json({ ok: true });
}
