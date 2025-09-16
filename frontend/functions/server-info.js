// Minimal Pages Functions handler that returns basic server info.
// This file was previously empty which caused Wrangler to warn "No routes found".
// Export a default fetch handler so Wrangler treats this as a Functions module.

export async function onRequestGet(context) {
	const { env, request } = context;
	const payload = {
		name: env && env.WORKER_NAME ? env.WORKER_NAME : 'moonwalking-pages',
		time: new Date().toISOString(),
		path: new URL(request.url).pathname,
	};

	return new Response(JSON.stringify(payload, null, 2), {
		status: 200,
		headers: { 'Content-Type': 'application/json' },
	});
}
