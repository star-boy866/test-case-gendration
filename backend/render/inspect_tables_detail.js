const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 3200, height: 6000 });

    const htmlPath = path.resolve(__dirname, 'docx-render.html');
    const fileUrl = 'file:///' + htmlPath.replace(/\\/g, '/');
    await page.goto(fileUrl);

    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/jszip/dist/jszip.min.js') });
    await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/docx-preview/dist/docx-preview.min.js') });

    const docxBuffer = fs.readFileSync('D:/test-case-gendration/healthcare-nl-testgen/TPL Rejection Error Handling Report Template (2).docx');
    const base64Data = docxBuffer.toString('base64');

    await page.evaluate(`renderDocx("${base64Data}")`);
    await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });

    const details = await page.evaluate(() => {
        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        return pages.map((p, pIdx) => {
            const tables = Array.from(p.querySelectorAll('table'));
            return {
                pageNumber: pIdx + 1,
                textSnippet: (p.innerText || '').slice(0, 200),
                tableCount: tables.length,
                tables: tables.map((t, tIdx) => {
                    const rows = Array.from(t.querySelectorAll('tr'));
                    return {
                        tableIndex: tIdx + 1,
                        rowCount: rows.length,
                        rows: rows.map((r, rIdx) => {
                            const cells = Array.from(r.querySelectorAll('td, th')).map(c => (c.innerText || '').trim().replace(/\n/g, ' '));
                            return {
                                rowIndex: rIdx + 1,
                                cellCount: cells.length,
                                cells: cells
                            };
                        })
                    };
                })
            };
        });
    });

    console.log(JSON.stringify(details, null, 2));

    await browser.close();
})();
