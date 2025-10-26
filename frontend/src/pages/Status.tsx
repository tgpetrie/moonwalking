import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export default function Status() {
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [swr, setSwr] = useState<any>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(console.error);
    api.metrics().then((m) => { setMetrics(m); setSwr(m?.swr); }).catch(console.error);
  }, []);

  return (
    <div style={{ padding: 16, fontFamily: 'ui-sans-serif, system-ui' }}>
      <h1>Local Status</h1>
      <h3>Health</h3>
      <pre>{JSON.stringify(health, null, 2)}</pre>
      <h3>Data Integrity</h3>
      <pre>{JSON.stringify(metrics?.data_integrity, null, 2)}</pre>
      <h3>SWR</h3>
      <pre>{JSON.stringify(swr, null, 2)}</pre>
    </div>
  );
}
