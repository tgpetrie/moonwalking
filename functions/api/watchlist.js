// Proxy for /api/watchlist
export async function onRequest({ request, env }) {
  if (!env.BACKEND_ORIGIN) {
    return new Response(JSON.stringify({ error: "BACKEND_ORIGIN missing" }), {
      status: 500,
      headers: { "content-type": "application/json" }
    });
  }

  try {
    const upstreamUrl = `${env.BACKEND_ORIGIN}/watchlist`;

    const response = await fetch(upstreamUrl, {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined
    });

    const responseBody = await response.text();

    return new Response(responseBody, {
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
