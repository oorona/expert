import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const slug = searchParams.get("slug");

  const url = slug
    ? backendUrl(`/api/documents/${slug}`)
    : backendUrl("/api/documents");

  const res = await fetch(url, { cache: "no-store", headers: authHeaders() });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const res = await fetch(backendUrl("/api/documents"), {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const docId = searchParams.get("id");
  const body = await request.json();
  const res = await fetch(backendUrl(`/api/documents/${docId}`), {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
