// Simple health check script for CI
import 'dotenv/config';

const url = `http://localhost:${process.env.PORT || 3100}/health`;
const abort = new AbortController();
const timeout = setTimeout(() => abort.abort(), 4000);

fetch(url, { signal: abort.signal })
  .then(r => r.json())
  .then(j => {
    if (j.status === 'ok') {
      console.log('HEALTH_OK');
      process.exit(0);
    } else {
      console.error('HEALTH_BAD', j);
      process.exit(2);
    }
  })
  .catch(e => {
    console.error('HEALTH_ERROR', e.message);
    process.exit(1);
  })
  .finally(() => clearTimeout(timeout));
