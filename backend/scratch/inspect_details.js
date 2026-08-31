const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const docxPath = path.resolve(__dirname, '../tests/fixtures/golden_sources/CR 18175 PRV-INT-027 UT DOCUMENT 1.docx');
    const docxBuffer = fs.readFileSync(docxPath);
    const base64Data = docxBuffer.toString('base64');
    
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 3200, height: 6000 });
    
    const htmlPath = path.resolve(__dirname, '../render/docx-render.html');
    await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/jszip/dist/jszip.min.js') });
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/docx-preview/dist/docx-preview.min.js') });
    
    await page.evaluate((b64) => renderDocx(b64), base64Data);
    await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });
    
    const details = await page.evaluate(() => {
        const sections = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        
        const sec3Paras = Array.from(sections[3].querySelectorAll('p, table, img')).map(el => {
            const tag = el.tagName.toLowerCase();
            if (tag === 'img') return `img src width=${el.naturalWidth}x${el.naturalHeight}`;
            return `${tag}: ${(el.innerText || '').trim().substring(0, 100)}`;
        });

        const sec4Paras = Array.from(sections[4].querySelectorAll('p, table, img')).map(el => {
            const tag = el.tagName.toLowerCase();
            if (tag === 'img') return `img src width=${el.naturalWidth}x${el.naturalHeight}`;
            return `${tag}: ${(el.innerText || '').trim().substring(0, 100)}`;
        });
        
        return { sec3Paras, sec4Paras };
    });
    
    console.log("SEC 3:", details.sec3Paras);
    console.log("SEC 4:", details.sec4Paras);
    await browser.close();
})();
