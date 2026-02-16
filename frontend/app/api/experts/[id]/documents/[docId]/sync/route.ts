import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  const res = await fetch(
    backendUrl(`/api/experts/${id}/documents/${docId}/sync`),
    { method: "POST", headers: authHeaders() }
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
