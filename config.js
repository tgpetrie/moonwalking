export function loadConfig() {
  const port = Number(process.env.PORT || 3100);
  const openAiKey = process.env.OPENAI_API_KEY || '';
  return { port, openAiKey };
}

export function assertConfig(cfg) {
  const missing = [];
  if (!cfg.openAiKey) missing.push('OPENAI_API_KEY');
  if (missing.length) {
    // Do not throw immediately to allow /health to respond, just warn.
    console.warn('Missing required env vars:', missing.join(', '));
  }
}
