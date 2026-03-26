const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const payload = await request.json();
  const upstream = await fetch(`${BACKEND_URL}/api/chat/reset`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      session_id: payload.session_id ?? "demo-session",
    }),
  });

  const bodyText = await upstream.text();

  return new Response(bodyText, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8",
    },
  });
}
