import { NextRequest, NextResponse } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  const res = await fetch(backendUrl(`/api/experts/${id}/documents/${docId}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    return NextResponse.json(
      { error: await res.text() },
      { status: res.status }
    );
  }
  return NextResponse.json({ ok: true });
}
