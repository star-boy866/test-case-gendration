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
    
    const pages = await page.$$('.docx-wrapper > section');
    let targetElement = null;
    
    // Strategy A: Check UT Document for Scenario 1 / report layout image
    for (let pIdx = 0; pIdx < pages.length; pIdx++) {
        const p = pages[pIdx];
        const paras = await p.$$('p');
        for (let i = 0; i < paras.length; i++) {
            const text = (await paras[i].innerText()).toLowerCase();
            if ((text.includes("scenario 1") || text.includes("layout")) && (text.includes("validated") || text.includes("dsd"))) {
                for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                    const prevText = (await paras[j - 1].innerText()).toLowerCase();
                    const img = await paras[j].$('img');
                    if (img && (prevText.includes("dsd") || text.includes("scenario 1"))) {
                        targetElement = img;
                        console.log(`[STAGE 3] LAYOUT_VALIDATION matched Scenario 1 DSD layout image on page ${pIdx + 1}.`);
                        break;
                    }
                }
                if (targetElement) break;
            }
        }
        if (targetElement) break;
    }
    
    if (targetElement) {
        await targetElement.screenshot({ path: path.resolve(__dirname, 'test_layout_out.png') });
        console.log("Saved test_layout_out.png!");
    } else {
        console.log("No element matched");
    }
    
    await browser.close();
})();
