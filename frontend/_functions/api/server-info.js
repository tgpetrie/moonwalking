export async function onRequest(context) {
  const { env } = context;

  // Debug: Check if function is being called
  console.log('Function called with BACKEND_ORIGIN:', env.BACKEND_ORIGIN);

  return new Response(JSON.stringify({
    debug: 'Function is working',
    backendOrigin: env.BACKEND_ORIGIN,
    timestamp: Date.now()
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
}
