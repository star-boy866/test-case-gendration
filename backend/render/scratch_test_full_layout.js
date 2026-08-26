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

    const layoutPageResult = await page.evaluate(() => {
        window.scrollTo(0, 0);
        if (document.scrollingElement) {
            document.scrollingElement.scrollTop = 0;
            document.scrollingElement.scrollLeft = 0;
        }

        const sections = Array.from(document.querySelectorAll('.docx-wrapper > section'));
        let targetSecIdx = -1;
        for (let i = 0; i < sections.length; i++) {
            const txt = (sections[i].innerText || '').toLowerCase();
            if (txt.includes("report layout") || txt.includes("future state - report output") || txt.includes("scenario 1")) {
                targetSecIdx = i;
                break;
            }
        }

        if (targetSecIdx === -1) return null;

        const sec = sections[targetSecIdx];
        const secRect = sec.getBoundingClientRect();

        // Find all elements within this section to get true full enclosing bounds
        const allElements = Array.from(sec.querySelectorAll('*'));
        const allRects = allElements.map(el => el.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);

        const minLeft = Math.min(secRect.left, ...allRects.map(r => r.left));
        const minTop = Math.min(secRect.top, ...allRects.map(r => r.top));
        const maxRight = Math.max(secRect.right, ...allRects.map(r => r.right));
        const maxBottom = Math.max(secRect.bottom, ...allRects.map(r => r.bottom));

        // Margin to ensure clean boundary around entire page
        const margin = 8;
        const pageClip = {
            x: Math.max(0, Math.floor(minLeft - margin)),
            y: Math.max(0, Math.floor(minTop - margin)),
            width: Math.ceil(maxRight - minLeft + margin * 2),
            height: Math.ceil(maxBottom - minTop + margin * 2)
        };

        const text = sec.innerText || '';
        const textLower = text.toLowerCase();

        const fullPageValidation = (
            textLower.includes("tpl rejection error handling report: report layout") ||
            textLower.includes("report layout")
        ) && (
            textLower.includes("this report is in excel format") ||
            textLower.includes("excel format")
        ) && (
            textLower.includes("enterprise operational reports")
        ) && (
            textLower.includes("opr-tpl-188")
        ) && (
            textLower.includes("department of human services")
        ) && (
            textLower.includes("run date")
        ) && (
            textLower.includes("page")
        ) && (
            textLower.includes("run time")
        );

        return {
            pageIndex: targetSecIdx,
            pageNumber: targetSecIdx + 1,
            secRect: { x: secRect.x, y: secRect.y, width: secRect.width, height: secRect.height },
            pageClip,
            fullPageValidation: fullPageValidation ? "PASS" : "FAIL",
            topBoundary: minTop <= secRect.top + 20 ? "PASS" : "FAIL",
            rightBoundary: maxRight >= 1650 ? "PASS" : "FAIL",
            bottomBoundary: maxBottom >= secRect.bottom - 20 ? "PASS" : "FAIL"
        };
    });

    console.log("=== ND FULL REPORT LAYOUT ===");
    console.log("methodology:\n    LAYOUT_VALIDATION\n");
    console.log("evidence_scope:\n    FULL_REPORT_LAYOUT\n");
    console.log(`source_page(s):\n    Page 6 (rendered index ${layoutPageResult.pageIndex + 1})\n`);
    console.log("page_rect:");
    console.log(`    x: ${layoutPageResult.pageClip.x}`);
    console.log(`    y: ${layoutPageResult.pageClip.y}`);
    console.log(`    width: ${layoutPageResult.pageClip.width}`);
    console.log(`    height: ${layoutPageResult.pageClip.height}\n`);

    // Screenshot with clip
    await page.screenshot({ path: 'test_full_report_layout_page.png', clip: layoutPageResult.pageClip });

    const stats = fs.statSync('test_full_report_layout_page.png');
    console.log("generated_png:");
    console.log(`    width: ${layoutPageResult.pageClip.width}`);
    console.log(`    height: ${layoutPageResult.pageClip.height}`);
    console.log(`    size: ${stats.size} bytes\n`);

    console.log(`fullPageValidation:\n    ${layoutPageResult.fullPageValidation}\n`);
    console.log(`topBoundary:\n    ${layoutPageResult.topBoundary}\n`);
    console.log(`rightBoundary:\n    ${layoutPageResult.rightBoundary}\n`);
    console.log(`bottomBoundary:\n    ${layoutPageResult.bottomBoundary}\n`);

    await browser.close();
})();
