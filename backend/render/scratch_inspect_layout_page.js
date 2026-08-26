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

    const pageInfo = await page.evaluate(() => {
        const sections = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        return sections.map((sec, idx) => {
            const text = sec.innerText || '';
            const rect = sec.getBoundingClientRect();
            const tables = Array.from(sec.querySelectorAll('table')).map(t => {
                const tr = t.getBoundingClientRect();
                return {
                    rect: { x: tr.x, y: tr.y, width: tr.width, height: tr.height },
                    rows: t.querySelectorAll('tr').length,
                    textSnippet: (t.innerText || '').slice(0, 100)
                };
            });
            const paras = Array.from(sec.querySelectorAll('p')).map(p => {
                const pr = p.getBoundingClientRect();
                return {
                    rect: { x: pr.x, y: pr.y, width: pr.width, height: pr.height },
                    text: (p.innerText || '').slice(0, 80)
                };
            });

            // Calculate bounding box enclosing all children of the section
            const allElements = Array.from(sec.querySelectorAll('*'));
            const allRects = allElements.map(el => el.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);
            const minX = Math.min(rect.left, ...allRects.map(r => r.left));
            const minY = Math.min(rect.top, ...allRects.map(r => r.top));
            const maxX = Math.max(rect.right, ...allRects.map(r => r.right));
            const maxY = Math.max(rect.bottom, ...allRects.map(r => r.bottom));

            return {
                pageIndex: idx,
                pageNumber: idx + 1,
                textLength: text.length,
                hasReportLayout: text.toLowerCase().includes("report layout"),
                sectionRect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                enclosingContentRect: {
                    x: minX,
                    y: minY,
                    width: maxX - minX,
                    height: maxY - minY
                },
                tables,
                parasSnippet: paras.slice(0, 5)
            };
        });
    });

    console.log("PAGE INFO:\n", JSON.stringify(pageInfo, null, 2));

    await browser.close();
})();
