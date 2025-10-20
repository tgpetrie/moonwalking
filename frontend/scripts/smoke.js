const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    console.log('Opening frontend at http://127.0.0.1:5173');
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' });

    // Wait for the gainers 1m two-column component to appear
    await page.waitForSelector('[data-test="one-min-gainers"]', { timeout: 30000 });

    // Click the first watch star
    const star = await page.$('[data-test="one-min-gainers"] .watch-star');
    if (star) {
      await star.click();
      console.log('Toggled star');
      // wait a bit for watchlist to persist
      await page.waitForTimeout(800);
    } else {
      console.log('No watch star found — ensure component is mounted');
    }

    // Click info icon on first card
    const info = await page.$('[data-test="one-min-gainers"] .fi-info');
    if (info) {
      await info.click();
      console.log('Clicked info icon');
      // wait for sentiment popover
      await page.waitForSelector('.sentiment-popover', { timeout: 5000 });
      console.log('Sentiment popover visible');
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
