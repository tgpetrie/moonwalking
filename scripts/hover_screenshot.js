const puppeteer = require('puppeteer-core');
const fs = require('fs');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1200, height: 900 });
    const url = 'http://127.0.0.1:5173/';
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

    // wait for rows to appear
    await page.waitForSelector('.table-row', { timeout: 10000 });

    // Hover first visible .table-row (assumed left / 1-min)
    const rows = await page.$$('.table-row');
    if (rows.length === 0) {
      console.error('No .table-row elements found');
      process.exit(1);
    }

  // Ensure first row is in view and hover it
  const leftRow = rows[0];
  await leftRow.evaluate(el => el.scrollIntoView({ block: 'center', inline: 'center' }));
  await new Promise(r => setTimeout(r, 120));
  await leftRow.hover();
  await new Promise(r => setTimeout(r, 200));

    // screenshot bounding box of the row (w/ padding)
    const box = await leftRow.boundingBox();
    if (box) {
      const pad = 8;
      await page.screenshot({
        path: 'screenshot_5173_hover_left.png',
        clip: {
          x: Math.max(0, box.x - pad),
          y: Math.max(0, box.y - pad),
          width: Math.min(1200, box.width + pad * 2),
          height: Math.min(900, box.height + pad * 2)
        }
      });
      console.log('Saved screenshot_5173_hover_left.png');
    } else {
      await page.screenshot({ path: 'screenshot_5173_hover_left.png', fullPage: false });
      console.log('Saved full-page screenshot_5173_hover_left.png fallback');
    }

    // Now find a .panel-3m .table-row with .is-loss (right panel)
    let rightRow = await page.$('.panel-3m .table-row.is-loss');
    if (!rightRow) {
      // fallback: pick first .panel-3m .table-row
      rightRow = await page.$('.panel-3m .table-row');
    }

    if (!rightRow) {
      console.error('No .panel-3m .table-row found for right hover');
    } else {
      await rightRow.evaluate(el => el.scrollIntoView({ block: 'center', inline: 'center' }));
      await new Promise(r => setTimeout(r, 120));
      await rightRow.hover();
      await new Promise(r => setTimeout(r, 200));
      const boxR = await rightRow.boundingBox();
      if (boxR) {
        const pad = 8;
        await page.screenshot({
          path: 'screenshot_5173_hover_right.png',
          clip: {
            x: Math.max(0, boxR.x - pad),
            y: Math.max(0, boxR.y - pad),
            width: Math.min(1200, boxR.width + pad * 2),
            height: Math.min(900, boxR.height + pad * 2)
          }
        });
        console.log('Saved screenshot_5173_hover_right.png');
      } else {
        await page.screenshot({ path: 'screenshot_5173_hover_right.png', fullPage: false });
        console.log('Saved full-page screenshot_5173_hover_right.png fallback');
      }
    }

    // Also capture a small scroll test: scroll the right panel a bit and screenshot
    const panel = await page.$('.panel-3m');
    if (panel) {
      await panel.evaluate(p => { p.scrollTop = 80; });
      await new Promise(r => setTimeout(r, 120));
      await page.screenshot({ path: 'screenshot_5173_panel3m_scrolled.png' });
      console.log('Saved screenshot_5173_panel3m_scrolled.png');
    }

  } catch (err) {
    console.error('Error during Puppeteer run:', err);
    process.exitCode = 2;
  } finally {
    await browser.close();
  }
})();
