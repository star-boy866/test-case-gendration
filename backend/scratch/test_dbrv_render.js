const { chromium } = require('playwright');
const docx = require('docx-preview');
const fs = require('fs');
const path = require('path');

async function testRender() {
    const docxPath = path.resolve('runs/210/source/source.docx');
    console.log("Loading DOCX from:", docxPath);
    const docxBuffer = fs.readFileSync(docxPath);
    const docxBase64 = docxBuffer.toString('base64');

    const htmlContent = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/docx-preview@0.3.3/dist/docx-preview.min.js"></script>
    <style>
        body { margin: 0; padding: 20px; background-color: #f1f5f9; }
        .docx-wrapper { background-color: transparent !important; padding: 0 !important; }
        .docx-wrapper > section { 
            background-color: white !important; 
            margin: 0 auto 30px auto !important; 
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1) !important;
            padding: 40px !important;
            box-sizing: border-box !important;
        }
    </style>
</head>
<body>
    <div id="container"></div>
    <script>
        const docxBlob = Uint8Array.from(atob("${docxBase64}"), c => c.charCodeAt(0));
        docx.renderAsync(docxBlob, document.getElementById("container"), null, {
            inWrapper: true,
            ignoreWidth: false,
            ignoreHeight: false,
            breakPages: true
        }).then(() => {
            window.DOCX_RENDERED = true;
        });
    </script>
</body>
</html>
    `;

    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 1400, height: 1800 });
    await page.setContent(htmlContent, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.DOCX_RENDERED === true, { timeout: 30000 });
    await page.waitForTimeout(1000);

    const result = await page.evaluate(() => {
        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        const pageInfo = [];

        pages.forEach((p, idx) => {
            const text = p.innerText || '';
            const tables = Array.from(p.querySelectorAll('table'));
            const hasReportBody = text.toLowerCase().includes("report body") || text.toLowerCase().includes("prov id");
            pageInfo.push({
                page: idx + 1,
                hasReportBody,
                tableCount: tables.length,
                textSnippet: text.slice(0, 100).replace(/\n+/g, ' ')
            });
        });

        // Search for Report Body table
        let foundBlock = null;
        for (let pIdx = 0; pIdx < pages.length; pIdx++) {
            const p = pages[pIdx];
            const pText = (p.innerText || '').toLowerCase();
            if (!pText.includes("report body") && !pText.includes("prov id")) continue;

            const tables = Array.from(p.querySelectorAll('table'));
            for (const t of tables) {
                const rows = Array.from(t.querySelectorAll('tr'));
                let inReportBody = false;
                let bodyHeadingRow = null;
                let headerRow = null;
                let mappingRows = [];
                let detectedTargets = [];

                for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                    const row = rows[rIdx];
                    const rText = (row.innerText || '').trim();
                    const rTextLower = rText.toLowerCase();

                    if (rTextLower === "report body" || (rTextLower.includes("report body") && rText.length < 40)) {
                        bodyHeadingRow = row;
                        inReportBody = true;
                    }

                    if (rTextLower.includes("field type") && rTextLower.includes("business label")) {
                        headerRow = row;
                        inReportBody = true;
                    }

                    // Check for next section stop
                    if (inReportBody && row !== bodyHeadingRow && row !== headerRow) {
                        if (
                            rTextLower.startsWith("report control break") ||
                            rTextLower.startsWith("report special processing") ||
                            rTextLower.startsWith("report output") ||
                            rTextLower.startsWith("report retention") ||
                            rTextLower.startsWith("report generation") ||
                            rTextLower.startsWith("report totals") ||
                            rTextLower.startsWith("report summary")
                        ) {
                            break;
                        }
                    }

                    if (inReportBody && row !== bodyHeadingRow && row !== headerRow) {
                        const cells = Array.from(row.querySelectorAll('td, th'));
                        if (cells.length >= 3) {
                            const cTexts = cells.map(c => (c.innerText || '').trim());
                            const hasTableOrCol = cTexts.some(txt => txt.includes("_TB") || txt.includes("P_") || txt.includes("T_") || txt.includes("R_") || txt.includes("Table") || txt.includes("Column"));
                            if (hasTableOrCol || rTextLower.includes("column") || rTextLower.includes("format") || rTextLower.includes("p_rpt")) {
                                mappingRows.push(row);
                                const label = cells.length >= 2 ? (cells[1].innerText || '').trim() : '';
                                if (label && !label.toLowerCase().includes("business label")) {
                                    detectedTargets.push(label);
                                }
                            }
                        }
                    }
                }

                if (mappingRows.length > 0) {
                    const allRelevantRows = [];
                    if (bodyHeadingRow) allRelevantRows.push(bodyHeadingRow);
                    if (headerRow && headerRow !== bodyHeadingRow) allRelevantRows.push(headerRow);
                    allRelevantRows.push(...mappingRows);

                    const rects = [];
                    allRelevantRows.forEach(r => {
                        rects.push(r.getBoundingClientRect());
                        r.querySelectorAll('td, th').forEach(c => rects.push(c.getBoundingClientRect()));
                    });

                    const minLeft = Math.min(...rects.map(r => r.left));
                    const minTop = Math.min(...rects.map(r => r.top));
                    const maxRight = Math.max(...rects.map(r => r.right));
                    const maxBottom = Math.max(...rects.map(r => r.bottom));

                    const margin = 4;
                    const finalCrop = {
                        x: Math.max(0, Math.floor(minLeft - margin)),
                        y: Math.max(0, Math.floor(minTop - margin)),
                        width: Math.ceil(maxRight - minLeft + margin * 2),
                        height: Math.ceil(maxBottom - minTop + margin * 2)
                    };

                    foundBlock = {
                        page: pIdx + 1,
                        detectedTargets,
                        mappingRowCount: mappingRows.length,
                        hasBodyHeading: !!bodyHeadingRow,
                        hasHeaderRow: !!headerRow,
                        finalCrop
                    };
                    break;
                }
            }
            if (foundBlock) break;
        }

        return { pageInfo, foundBlock };
    });

    console.log("Pages Info:", JSON.stringify(result.pageInfo, null, 2));
    console.log("Found Block:", JSON.stringify(result.foundBlock, null, 2));

    if (result.foundBlock) {
        const outPath = path.resolve('scratch/test_dbrv_full_snapshot.png');
        await page.screenshot({ path: outPath, clip: result.foundBlock.finalCrop });
        console.log("Saved test screenshot to:", outPath);
    }

    await browser.close();
}

testRender().catch(console.error);
