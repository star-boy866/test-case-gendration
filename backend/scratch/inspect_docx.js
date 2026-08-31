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
    
    const pageInfo = await page.evaluate(() => {
        const sections = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        return sections.map((s, idx) => {
            const paras = Array.from(s.querySelectorAll('p, h1, h2, h3, h4, h5, table'));
            const elements = paras.map(p => {
                const tag = p.tagName.toLowerCase();
                const text = (p.innerText || '').trim().replace(/\n/g, ' [NL] ');
                return `${tag}: ${text.substring(0, 80)}`;
            }).slice(0, 10);
            return {
                idx,
                textSnippet: (s.innerText || '').substring(0, 200).replace(/\n/g, ' | '),
                elements,
                tablesCount: s.querySelectorAll('table').length,
                imagesCount: s.querySelectorAll('img').length
            };
        });
    });
    
    console.log(JSON.stringify(pageInfo, null, 2));
    await browser.close();
})();
