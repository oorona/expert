import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const res = await fetch(backendUrl(`/api/search?${searchParams}`), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
