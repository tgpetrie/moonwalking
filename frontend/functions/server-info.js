export async function onRequest(request) {
  return new Response(JSON.stringify({
    debug: 'Function is working',
    timestamp: Date.now()
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}
