import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

async function proxyRequest(request: NextRequest, path: string) {
  const qs = request.nextUrl.search;
  const url = backendUrl(`/api/admin/${path}${qs}`);
  const init: RequestInit = {
    method: request.method,
    headers: authHeaders({ "Content-Type": "application/json" }),
  };

  if (request.method !== "GET" && request.method !== "DELETE") {
    init.body = await request.text();
  }

  const res = await fetch(url, init);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path.join("/"));
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path.join("/"));
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path.join("/"));
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  return proxyRequest(request, path.join("/"));
}
