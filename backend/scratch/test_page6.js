const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const docxPath = 'd:/test-case-gendration/healthcare-nl-testgen/ND-RP-07-0002 DSD.docx';
    const base64Data = fs.readFileSync(docxPath).toString('base64');
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 2400, height: 12000 });
    const htmlPath = path.resolve(__dirname, '../render/docx-render.html');
    await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/jszip/dist/jszip.min.js') });
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/docx-preview/dist/docx-preview.min.js') });
    await page.evaluate(`renderDocx("${base64Data}")`);
    await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });

    const pages = await page.$$('.docx-wrapper > section');
    const page6 = pages[5];
    await page6.screenshot({
        path: 'd:/test-case-gendration/healthcare-nl-testgen/backend/scratch/page6_layout_design.png'
    });

    console.log('Saved page6_layout_design.png successfully via element screenshot');
    await browser.close();
})();
