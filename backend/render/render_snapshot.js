const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const args = process.argv.slice(2);
    if (args.length < 4) {
        console.error("Usage: node render_snapshot.js <docxPath> <outPngPath> <semanticSection> <reportId>");
        process.exit(1);
    }

    const docxPath = args[0];
    const outPngPath = args[1];
    const semanticSection = args[2];
    const reportId = args[3];

    if (!fs.existsSync(docxPath)) {
        console.error(`File not found: ${docxPath}`);
        process.exit(1);
    }

    const docxBuffer = fs.readFileSync(docxPath);
    const base64Data = docxBuffer.toString('base64');

    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    try {
        const htmlPath = path.resolve(__dirname, 'docx-render.html');
        // Use file:// protocol with posix-style path for Windows compatibility
        const fileUrl = 'file:///' + htmlPath.replace(/\\/g, '/');
        await page.goto(fileUrl);

        // Inject the dependencies
        await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/jszip/dist/jszip.min.js') });
        await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/docx-preview/dist/docx-preview.min.js') });

        // Trigger rendering
        await page.evaluate(`renderDocx("${base64Data}")`);

        // Wait for rendering to complete
        await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });

        const renderError = await page.evaluate('window.renderError');
        if (renderError) {
            throw new Error(`Rendering failed in browser: ${renderError}`);
        }

        // Find the right page section based on the heuristic
        // docx-preview wrapper generates <section class="docx"> for each page
        const pages = await page.$$('.docx-wrapper > section');
        
        if (pages.length === 0) {
            throw new Error("No pages rendered");
        }

        let targetPage = pages[0]; // fallback to first
        let found = false;

        for (const p of pages) {
            const innerText = await p.innerText();
            const textLower = innerText.toLowerCase();
            const secLower = semanticSection.toLowerCase();
            const repLower = reportId.toLowerCase();
            
            const hasSection = secLower ? textLower.includes(secLower) : false;
            const hasReportId = repLower ? textLower.includes(repLower) : false;
            
            if (hasSection && hasReportId) {
                targetPage = p;
                found = true;
                break;
            } else if (hasSection && !found) {
                targetPage = p;
                found = true;
            }
        }

        // Ensure output directory exists
        const outDir = path.dirname(outPngPath);
        if (!fs.existsSync(outDir)) {
            fs.mkdirSync(outDir, { recursive: true });
        }

        // Take a screenshot of the specific section element
        await targetPage.screenshot({ path: outPngPath });
        console.log(`Successfully generated snapshot at ${outPngPath}`);

    } catch (err) {
        console.error(err);
        process.exit(1);
    } finally {
        await browser.close();
    }
})();
