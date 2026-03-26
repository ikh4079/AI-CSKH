const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: Request) {
  const payload = await request.json();
  const upstream = await fetch(`${BACKEND_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: payload.messages.at(-1)?.content ?? "",
      session_id: payload.session_id ?? "demo-session",
      user_id: payload.user_id ?? "portfolio-user",
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text();
    return Response.json(
      {
        error: "Backend chat stream failed",
        detail,
      },
      { status: upstream.status || 500 },
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "X-Accel-Buffering": "no",
      "X-Trace-Id": upstream.headers.get("x-trace-id") ?? "",
      "X-Tool-Calls": upstream.headers.get("x-tool-calls") ?? "[]",
      "X-Tool-Payloads": upstream.headers.get("x-tool-payloads") ?? "[]",
    },
  });
}
