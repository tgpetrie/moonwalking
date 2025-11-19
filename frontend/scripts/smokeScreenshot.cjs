const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  const url = process.env.SMOKE_URL || 'http://127.0.0.1:5173/';
  console.log('Opening', url);
  const browser = await puppeteer.launch({ args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setViewport({ width: 1280, height: 900 });
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
  await page.waitForTimeout(500);
  const out = 'frontend/smoke.png';
  await page.screenshot({ path: out, fullPage: true });
  console.log('Saved screenshot to', out);
  await browser.close();
})();

