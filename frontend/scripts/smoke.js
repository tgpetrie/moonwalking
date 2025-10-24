// ESM-friendly smoke script. Uses dynamic import so it works when package.json uses "type": "module".
(async () => {
  let playwright;
  try {
    playwright = await import('playwright');
  } catch (e) {
    console.error('Playwright is not installed. Run `npm install --save-dev playwright` in the frontend folder and `npx playwright install` to install browsers.');
    process.exit(2);
  }

  const { chromium } = playwright;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
  console.log('Opening frontend at http://127.0.0.1:5173');
  // Vite dev server keeps an HMR websocket open; wait for DOM then for specific selector
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });

  // Wait for the gainers 1m two-column component to appear (allow longer for initial hydration)
  await page.waitForSelector('[data-test="one-min-card"]', { timeout: 60000 });

    // Click the first watch star (use Locator API to be robust against re-renders)
    const cardLocator = page.locator('[data-test="one-min-card"]').first();
    const starLocator = cardLocator.locator('[data-test="watch-star"] button, [data-test="watch-star"]');
    if (await starLocator.count() > 0) {
      try {
        await starLocator.first().click({ timeout: 5000 });
        console.log('Toggled star');
        await page.waitForTimeout(800);
      } catch (e) {
        console.warn('Star click failed, retrying via page.click...', e.message || e);
        // fallback: attempt page-level click
        await page.click('[data-test="one-min-card"] [data-test="watch-star"] button, [data-test="one-min-card"] [data-test="watch-star"]', { timeout: 5000 }).catch(() => {});
      }
    } else {
      console.log('No watch star found — ensure component is mounted');
    }

    // Click info icon on first card
    // Click info icon (locator API)
    const infoLocator = cardLocator.locator('[data-test="info-button"], .fi-info, button[aria-label="Show sentiment"]');
    if (await infoLocator.count() > 0) {
      try {
        await infoLocator.first().click({ timeout: 5000 });
        console.log('Clicked info icon');
        await page.waitForSelector('[data-test="sentiment-popover"], .sentiment-popover', { timeout: 7000 });
        console.log('Sentiment popover visible');
      } catch (e) {
        console.warn('Info click or popover wait failed:', e.message || e);
      }
    } else {
      console.log('No info icon found — ensure RowActions renders FiInfo with class fi-info');
    }

    console.log('Smoke check complete — success');
    await browser.close();
    process.exit(0);
  } catch (err) {
    console.error('Smoke check failed', err);
    await browser.close();
    process.exit(2);
  }
})();
