const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const docxPath = 'd:/test-case-gendration/healthcare-nl-testgen/ND-RP-07-0002 DSD.docx';
    const base64Data = fs.readFileSync(docxPath).toString('base64');
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 2400, height: 4000 });
    const htmlPath = path.resolve(__dirname, '../render/docx-render.html');
    await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/jszip/dist/jszip.min.js') });
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/docx-preview/dist/docx-preview.min.js') });
    await page.evaluate(`renderDocx("${base64Data}")`);
    await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });

    const pages = await page.$$('.docx-wrapper > section');
    for (let pIdx of [3, 5, 7]) { // 0-indexed for Pages 4, 6, 8
        const p = pages[pIdx];
        const tables = await p.$$('table');
        console.log(`\n=================== PAGE ${pIdx + 1} (${tables.length} tables) ===================`);
        for (let tIdx = 0; tIdx < tables.length; tIdx++) {
            const rows = await tables[tIdx].$$('tr');
            console.log(`--- Table ${tIdx + 1} (${rows.length} rows) ---`);
            for (let rIdx = 0; rIdx < Math.min(5, rows.length); rIdx++) {
                const text = (await rows[rIdx].innerText()).replace(/\n/g, ' | ').trim();
                console.log(`  Row ${rIdx + 1}: ${text.slice(0, 120)}`);
            }
        }
    }
    await browser.close();
})();
