import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await fetch(backendUrl(`/api/experts/${id}/store-info`), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
