const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const docxPath = path.resolve('runs/210/source/source.docx');
    const docxBuffer = fs.readFileSync(docxPath);
    const base64Data = docxBuffer.toString('base64');
    
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 3200, height: 6000 });
    
    const htmlPath = path.resolve('render/docx-render.html');
    await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
    await page.addScriptTag({ path: path.resolve('node_modules/jszip/dist/jszip.min.js') });
    await page.addScriptTag({ path: path.resolve('node_modules/docx-preview/dist/docx-preview.min.js') });
    
    await page.evaluate((b64) => renderDocx(b64), base64Data);
    await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });
    
    const tableInfo = await page.evaluate(() => {
        const tables = Array.from(document.querySelectorAll('table'));
        return tables.map((t, idx) => {
            const rect = t.getBoundingClientRect();
            return {
                idx,
                text: (t.innerText || '').substring(0, 100).replace(/\n/g, ' [NL] '),
                rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
            };
        });
    });
    
    console.log(JSON.stringify(tableInfo, null, 2));
    await browser.close();
})();
