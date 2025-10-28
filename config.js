export function loadConfig() {
  // Default dev server port: prefer 5100 to avoid conflicting local stacks
  const port = Number(process.env.PORT || 5100);
  const host = process.env.HOST || '127.0.0.1';
  const openAiKey = process.env.OPENAI_API_KEY || '';
  return { port, host, openAiKey };
}

export function assertConfig(cfg) {
  const missing = [];
  if (!cfg.openAiKey) missing.push('OPENAI_API_KEY');
  if (missing.length) {
    // Do not throw immediately to allow /health to respond, just warn.
    console.warn('Missing required env vars:', missing.join(', '));
  }
}
