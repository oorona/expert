import { NextRequest } from "next/server";
import { backendUrl, authHeaders } from "@/lib/backend";

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  const { id } = await context.params;
  const body = await request.json();
  const res = await fetch(
    backendUrl(`/api/incidents/${id}/infographic`),
    {
      method: "PATCH",
      headers: {
        ...authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }
  );

  const data = await res.json();
  return Response.json(data, { status: res.status });
}
