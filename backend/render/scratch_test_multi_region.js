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

    const resolutionResult = await page.evaluate(() => {
        window.scrollTo(0, 0);
        if (document.scrollingElement) {
            document.scrollingElement.scrollTop = 0;
            document.scrollingElement.scrollLeft = 0;
        }

        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        let regions = [];
        let allLabelsFound = [];

        for (let pIdx = 0; pIdx < pages.length; pIdx++) {
            const p = pages[pIdx];
            const pText = (p.innerText || '').toLowerCase();
            
            // Check if page belongs to Report Layout or Report Body or Report Specification
            const isLayout = pText.includes("report layout") || pText.includes("excel format");
            const isSpec = pText.includes("report specification") || pText.includes("report body");

            if (!isLayout && !isSpec) continue;

            const tables = Array.from(p.querySelectorAll('table'));
            for (let tIdx = 0; tIdx < tables.length; tIdx++) {
                const t = tables[tIdx];
                const rows = Array.from(t.querySelectorAll('tr'));
                for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                    const r = rows[rIdx];
                    const cells = Array.from(r.querySelectorAll('td, th'));
                    if (cells.length < 3) continue;

                    // Extract candidate column labels from cells
                    const cellTexts = cells.map(c => (c.innerText || '').trim()).filter(Boolean);
                    
                    // Filter out report header or metadata rows
                    const joined = cellTexts.join(' ').toLowerCase();
                    if (joined.includes("enterprise") || joined.includes("department of human") || joined.includes("run date") || joined.includes("page: x of y")) {
                        continue;
                    }

                    // Check if this row represents a column label header row (at least 3 non-empty columns with uppercase/business names)
                    const labelCandidates = cellTexts.filter(txt => {
                        const l = txt.toLowerCase();
                        return !l.includes("source:") && !l.includes("run date") && !l.includes("change control") && txt.length > 1 && txt.length < 60;
                    });

                    // In ND Report Layout, header rows have 15 distinct column labels
                    if (labelCandidates.length >= 4) {
                        // Check if row has sample row below it
                        let nextRow = rows[rIdx + 1] || null;
                        const rBox = r.getBoundingClientRect();
                        let bottom = rBox.bottom;
                        if (nextRow) {
                            const nrBox = nextRow.getBoundingClientRect();
                            // If next row contains sample data (XXXXXXX / MM/DD/YYYY / 999), include it
                            const nrText = (nextRow.innerText || '').trim();
                            if (nrText.includes("XXX") || nrText.includes("999") || nrText.includes("MM/DD")) {
                                bottom = nrBox.bottom;
                            }
                        }

                        // Get full width of the table / row cells
                        const cellBoxes = cells.map(c => c.getBoundingClientRect()).filter(b => b.width > 0);
                        const minLeft = Math.min(...cellBoxes.map(b => b.left), rBox.left);
                        const maxRight = Math.max(...cellBoxes.map(b => b.right), rBox.right);
                        const minTop = rBox.top;

                        const margin = 4;
                        const crop = {
                            x: Math.max(0, Math.floor(minLeft - margin)),
                            y: Math.max(0, Math.floor(minTop - margin)),
                            width: Math.ceil(maxRight - minLeft + margin * 2),
                            height: Math.ceil(bottom - minTop + margin * 2)
                        };

                        regions.push({
                            pageIndex: pIdx,
                            pageNumber: pIdx + 1,
                            rowIndex: rIdx + 1,
                            labelsFound: labelCandidates,
                            crop
                        });

                        allLabelsFound.push(...labelCandidates);
                    }
                }
            }
        }

        return {
            regions,
            totalFound: allLabelsFound.length,
            labels: allLabelsFound
        };
    });

    console.log("RESOLUTION RESULT:\n", JSON.stringify(resolutionResult, null, 2));

    await browser.close();
})();
