import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get("session_id");
  const incoming = searchParams.get("incoming");

  let url: string;
  if (incoming === "true") {
    const offset = searchParams.get("offset") || "0";
    const limit = searchParams.get("limit") || "50";
    url = backendUrl(`/api/incidents/incoming?offset=${offset}&limit=${limit}`);
  } else if (sessionId) {
    url = backendUrl(`/api/incidents/${sessionId}`);
  } else {
    const qs = request.nextUrl.search;
    url = backendUrl(`/api/incidents${qs}`);
  }

  const res = await fetch(url, { cache: "no-store", headers: authHeaders() });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PATCH(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const incidentId = searchParams.get("id");
  const action = searchParams.get("action");

  if (!incidentId) {
    return Response.json({ error: "Missing id" }, { status: 400 });
  }

  const body = await request.text();

  let url: string;
  if (action === "status") {
    url = backendUrl(`/api/incidents/${incidentId}/status`);
  } else {
    url = backendUrl(`/api/incidents/${incidentId}`);
  }

  const res = await fetch(url, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body,
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const incidentId = searchParams.get("id");

  // Bulk delete all incidents (no id param)
  if (!incidentId) {
    const res = await fetch(backendUrl("/api/incidents"), {
      method: "DELETE",
      headers: authHeaders(),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  }

  const res = await fetch(backendUrl(`/api/incidents/${incidentId}`), {
    method: "DELETE",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
