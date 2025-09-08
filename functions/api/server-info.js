export async function onRequest({ env }) {
  const id = env.HUB.idFromName('global');
  return env.HUB.get(id).fetch('https://do.internal/server-info');
}

