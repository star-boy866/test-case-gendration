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

    const labelMeasure = await page.evaluate(() => {
        window.scrollTo(0, 0);
        if (document.scrollingElement) {
            document.scrollingElement.scrollTop = 0;
            document.scrollingElement.scrollLeft = 0;
        }

        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        let blocks = [];
        let allSeenLabels = new Set();
        let pageLabelsMap = {};

        for (let pIdx = 0; pIdx < pages.length; pIdx++) {
            const p = pages[pIdx];
            const pText = (p.innerText || '').toLowerCase();
            if (!pText.includes("report layout") && !pText.includes("excel format")) continue;

            const tables = Array.from(p.querySelectorAll('table'));
            for (let tIdx = 0; tIdx < tables.length; tIdx++) {
                const t = tables[tIdx];
                // Check if table is a nested column header table
                const rows = Array.from(t.querySelectorAll('tr'));
                for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                    const r = rows[rIdx];
                    const cells = Array.from(r.querySelectorAll('td, th'));
                    if (cells.length < 4) continue;

                    const cellTexts = cells.map(c => (c.innerText || '').trim()).filter(Boolean);
                    
                    // Column labels: uppercase business field names (no 'Source:', 'Run Date:', etc.)
                    const isHeaderRow = cellTexts.every(txt => {
                        const l = txt.toLowerCase();
                        return !l.includes("source:") && !l.includes("mm/dd") && !l.includes("change control") && !txt.startsWith("XXX") && !txt.startsWith("999");
                    });

                    if (isHeaderRow && cellTexts.length >= 4) {
                        // Check if these labels are new
                        const newLabels = cellTexts.filter(l => !allSeenLabels.has(l));
                        if (newLabels.length >= 4) {
                            newLabels.forEach(l => allSeenLabels.add(l));

                            const pNum = pIdx + 1;
                            if (!pageLabelsMap[pNum]) pageLabelsMap[pNum] = [];
                            pageLabelsMap[pNum].push(...newLabels);

                            // Determine full table/row crop including sample row
                            let nextRow = rows[rIdx + 1] || null;
                            const rBox = r.getBoundingClientRect();
                            let bottom = rBox.bottom;
                            if (nextRow) {
                                const nrBox = nextRow.getBoundingClientRect();
                                const nrText = (nextRow.innerText || '').trim();
                                if (nrText.includes("XXX") || nrText.includes("999") || nrText.includes("MM/DD") || nrText.includes("Error")) {
                                    bottom = nrBox.bottom;
                                }
                            }

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

                            blocks.push({
                                pageIndex: pIdx,
                                pageNumber: pNum,
                                labels: newLabels,
                                labelCount: newLabels.length,
                                crop
                            });
                        }
                    }
                }
            }
        }

        return {
            blocks,
            pageLabelsMap,
            totalFound: allSeenLabels.size,
            labels: Array.from(allSeenLabels)
        };
    });

    console.log("=== ND LABEL EVIDENCE RESOLUTION ===");
    console.log(`expected_labels = 30\n`);
    
    // Page 8 (mapped to page 8 in ND DSD) and Page 9
    const pKeys = Object.keys(labelMeasure.pageLabelsMap);
    pKeys.forEach((k, idx) => {
        const dsdPageNum = 8 + idx; // Maps to ND DSD page 8, 9
        const lbls = labelMeasure.pageLabelsMap[k];
        console.log(`page ${dsdPageNum}:`);
        console.log(`    labels_found = ${lbls.length}`);
        console.log(`    labels = ${lbls.join(', ')}\n`);
    });

    console.log(`total_found = ${labelMeasure.totalFound}`);
    console.log(`evidence_complete = ${labelMeasure.totalFound >= 30 ? 'YES' : 'NO'}`);

    if (labelMeasure.totalFound < 30) {
        throw new Error(`ND LABEL_VALIDATION failed: found ${labelMeasure.totalFound} of 30 expected labels.`);
    }

    // Step 2: Take screenshots of each block
    const blockBuffers = [];
    for (let i = 0; i < labelMeasure.blocks.length; i++) {
        const crop = labelMeasure.blocks[i].crop;
        const buf = await page.screenshot({ clip: crop });
        blockBuffers.push({ buf, crop });
    }

    // Step 3: Stitch vertically using browser Canvas
    const stitchPage = await browser.newPage();
    const totalHeight = blockBuffers.reduce((acc, b) => acc + b.crop.height, 0) + (blockBuffers.length - 1) * 12; // 12px separator
    const maxWidth = Math.max(...blockBuffers.map(b => b.crop.width));

    await stitchPage.setViewportSize({ width: maxWidth + 50, height: totalHeight + 50 });

    const base64Images = blockBuffers.map(b => b.buf.toString('base64'));

    const stitchedBase64 = await stitchPage.evaluate(async ({ base64Images, maxWidth, totalHeight, blockHeights }) => {
        const canvas = document.createElement('canvas');
        canvas.width = maxWidth;
        canvas.height = totalHeight;
        const ctx = canvas.getContext('2d');

        // Clean slate/navy background
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        let currentY = 0;
        for (let i = 0; i < base64Images.length; i++) {
            const img = new Image();
            img.src = 'data:image/png;base64,' + base64Images[i];
            await new Promise(r => img.onload = r);

            ctx.drawImage(img, 0, currentY);
            currentY += blockHeights[i];

            if (i < base64Images.length - 1) {
                // Draw a sleek separator
                ctx.fillStyle = '#1e293b';
                ctx.fillRect(0, currentY, canvas.width, 12);
                ctx.fillStyle = '#475569';
                ctx.fillRect(0, currentY + 5, canvas.width, 2);
                currentY += 12;
            }
        }

        return canvas.toDataURL('image/png').split(',')[1];
    }, {
        base64Images,
        maxWidth,
        totalHeight,
        blockHeights: blockBuffers.map(b => b.crop.height)
    });

    const finalBuffer = Buffer.from(stitchedBase64, 'base64');
    fs.writeFileSync('test_stitched_labels.png', finalBuffer);
    console.log(`Saved test_stitched_labels.png (${finalBuffer.length} bytes, dimensions: ${maxWidth}x${totalHeight})`);

    await stitchPage.close();
    await browser.close();
})();
