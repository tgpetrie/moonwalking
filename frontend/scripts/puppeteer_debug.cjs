const puppeteer = require('puppeteer');
(async () => {
  const url = process.env.SMOKE_URL || 'http://127.0.0.1:5173/';
  console.log('Opening', url);
  const browser = await puppeteer.launch({ args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.on('console', msg => console.log('PAGE LOG:', msg.type(), msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  page.on('requestfailed', req => console.log('REQUEST FAILED:', req.url(), req.failure && req.failure().errorText));
  page.on('response', resp => console.log('RESPONSE:', resp.status(), resp.url()));
  page.setViewport({ width: 1280, height: 900 });
  try {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
    await page.waitForTimeout(1000);
    const out = '/tmp/smoke_debug.png';
    await page.screenshot({ path: out, fullPage: true });
    console.log('Saved screenshot to', out);
  } catch (err) {
    console.error('GOTO ERROR:', err && err.message);
  }
  await browser.close();
})();
