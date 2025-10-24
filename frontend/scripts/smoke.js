// Playwright smoke: waits for one-min card, surfaces useful diagnostics on failure.
(async () => {
  let playwright;
  try {
    playwright = await import('playwright');
  } catch (e) {
    console.error(
      'Playwright is not installed. Run `npm install --save-dev playwright` in the frontend folder and `npx playwright install` to install browsers.'
    );
    process.exit(2);
  }

  const { chromium } = playwright;
  const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:5173';
  const TARGET = `${BASE_URL.replace(/\/$/, '')}/`;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') {
      console.log(`[console.${type}] ${msg.text()}`);
    }
  });

  try {
    const timeoutMs = 120_000;
    console.log(`Opening frontend at ${TARGET}`);
    await page.goto(TARGET, { waitUntil: 'domcontentloaded', timeout: timeoutMs });

    await page.waitForSelector('[data-test="one-min-card"]', { timeout: timeoutMs });
    const rowCount = await page.locator('[data-test="one-min-card"] tbody tr').count();
    if (rowCount === 0) {
      throw new Error('No rows rendered under one-min-card.');
    }

    console.log(`SMOKE OK: one-min-card present, rows = ${rowCount}`);
    await browser.close();
    process.exit(0);
  } catch (err) {
    try {
      await page.screenshot({ path: 'smoke_fail.png', fullPage: true });
    } catch {
      // ignore screenshot errors
    }
    let html = '';
    try {
      html = await page.content();
    } catch {
      // ignore HTML capture errors
    }
    console.error('SMOKE FAIL:', err?.message || err);
    if (html) {
      console.log('=== HTML HEAD (first 2000 chars) ===');
      console.log(html.slice(0, 2000));
    }
    await browser.close();
    process.exit(1);
  }
})();
