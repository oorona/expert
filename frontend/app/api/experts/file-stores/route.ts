import { backendUrl, authHeaders } from "@/lib/backend";

export async function GET() {
  const res = await fetch(backendUrl("/api/experts/file-stores"), {
    cache: "no-store",
    headers: authHeaders(),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
