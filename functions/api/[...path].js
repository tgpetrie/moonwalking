// Simple proxy for /api/* requests
export async function onRequest({ request, env }) {
  if (!env.BACKEND_ORIGIN) {
    return new Response(JSON.stringify({ error: "BACKEND_ORIGIN missing" }), {
      status: 500,
      headers: { "content-type": "application/json" }
    });
  }

  try {
    const url = new URL(request.url);
    const upstreamUrl = `${env.BACKEND_ORIGIN}${url.pathname.replace(/^\/api/, "")}${url.search}`;

    const response = await fetch(upstreamUrl, {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined
    });

    return new Response(response.body, {
      status: response.status,
      headers: response.headers
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "content-type": "application/json" }
    });
  }
}
