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
    
    // Find Report Layout page (contains 'Report Layout')
    let layoutPage = null;
    let specTable = null;

    for (let p of pages) {
        const text = (await p.innerText()).toLowerCase();
        if (text.includes('report layout') && text.includes('enterprise operational reports')) {
            layoutPage = p;
        }
        if (text.includes('report specification') || text.includes('report body')) {
            const tables = await p.$$('table');
            for (let t of tables) {
                const tText = (await t.innerText()).toLowerCase();
                if (tText.includes('report body') && tText.includes('field label')) {
                    specTable = t;
                    break;
                }
            }
        }
    }

    console.log('Found layoutPage:', !!layoutPage, 'Found specTable:', !!specTable);

    const layoutBuf = await layoutPage.screenshot();
    const specBuf = await specTable.screenshot();

    // Stitch together using browser evaluate canvas
    const stitchedBase64 = await page.evaluate(async ({ lB64, sB64 }) => {
        const loadImg = (src) => new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = src;
        });

        const img1 = await loadImg('data:image/png;base64,' + lB64);
        const img2 = await loadImg('data:image/png;base64,' + sB64);

        const canvas = document.createElement('canvas');
        const gap = 30;
        const width = Math.max(img1.width, img2.width);
        const height = img1.height + img2.height + gap;
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(0, 0, width, height);

        // Draw Layout Image
        ctx.drawImage(img1, (width - img1.width) / 2, 0);

        // Draw Separator Line / Label
        ctx.fillStyle = '#0284c7';
        ctx.fillRect(0, img1.height + 10, width, 4);

        // Draw Spec Table Image
        ctx.drawImage(img2, (width - img2.width) / 2, img1.height + gap);

        return canvas.toDataURL('image/png').split(',')[1];
    }, {
        lB64: layoutBuf.toString('base64'),
        sB64: specBuf.toString('base64')
    });

    fs.writeFileSync('d:/test-case-gendration/healthcare-nl-testgen/backend/scratch/stitched_labels_and_layout.png', Buffer.from(stitchedBase64, 'base64'));
    console.log('Saved stitched_labels_and_layout.png');
    await browser.close();
})();
