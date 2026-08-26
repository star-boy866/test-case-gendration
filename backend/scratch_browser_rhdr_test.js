const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const page = await context.newPage();

    const consoleLogs = [];
    page.on('console', msg => {
        const txt = msg.text();
        consoleLogs.push(txt);
        console.log('[BROWSER CONSOLE]', txt);
    });

    const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvYnVsaSIsInJvbGUiOiJhZG1pbiIsImlhdCI6MTc4NzY1OTU1OCwiZXhwIjoxNzg3Njg4MzU4fQ.BZpmQP129UH6xhY6dXSBwXPIPBtNb0oitQeeCbQmO8o';

    // Inject valid token directly into localStorage
    await page.addInitScript((tok) => {
        localStorage.setItem('healthcare_nl_testgen_token', tok);
        localStorage.setItem('user', JSON.stringify({ id: 1, username: 'obuli', role: 'admin' }));
    }, token);

    console.log('1. Navigating to /cognos...');
    await page.goto('http://localhost:5173/cognos', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(1500);

    // 2. Upload ND file
    const docxPath = 'D:\\test-case-gendration\\healthcare-nl-testgen\\TPL Rejection Error Handling Report Template (2).docx';
    console.log('2. Uploading DOCX:', docxPath);
    const fileInput = await page.$('input[type="file"]');
    if (fileInput) {
        await fileInput.setInputFiles(docxPath);
        await page.waitForTimeout(2500);

        const generateBtn = await page.$('button:has-text("Generate Intelligence")');
        if (generateBtn) {
            console.log('3. Clicking Generate Intelligence...');
            await generateBtn.click();
            console.log('4. Waiting for generation to finish...');
            await page.waitForSelector('button:has-text("Execution Scenarios")', { timeout: 90000 });
            console.log('Generation completed!');
        }
    }

    // 5. Click Execution Scenarios tab
    console.log('5. Clicking Execution Scenarios tab...');
    await page.click('button:has-text("Execution Scenarios")');
    await page.waitForTimeout(2500);

    // 6. Select explicitly OPR188-RHDR-01
    console.log('6. Selecting OPR188-RHDR-01...');
    const rhdrBtn = await page.$('tr:has-text("OPR188-RHDR-01"), td:has-text("OPR188-RHDR-01")');
    if (rhdrBtn) {
        console.log('Found OPR188-RHDR-01, clicking it...');
        await rhdrBtn.click();
        await page.waitForTimeout(2500);
    } else {
        console.log('OPR188-RHDR-01 not visible in first rows, searching table...');
        const allTrs = await page.$$('table tbody tr');
        for (const tr of allTrs) {
            const text = await tr.innerText();
            if (text.includes('OPR188-RHDR-01') || text.includes('RHDR')) {
                console.log('Clicking matched tr:', text.slice(0, 50));
                await tr.click();
                await page.waitForTimeout(2500);
                break;
            }
        }
    }

    // 7. Wait for DSD Evidence Preview to load
    console.log('7. Waiting for DSD Evidence Preview...');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: 'test_rhdr_preview_card.png' });
    console.log('Saved test_rhdr_preview_card.png');

    // 8. Click Open Full Size
    console.log('8. Clicking Open Full Size...');
    const fullSizeBtn = await page.$('button:has-text("Open Full Size")');
    if (fullSizeBtn) {
        await fullSizeBtn.click();
        await page.waitForTimeout(3000);
        await page.screenshot({ path: 'test_rhdr_modal_full.png' });
        console.log('Saved test_rhdr_modal_full.png');
    }

    fs.writeFileSync('browser_console_output_rhdr.json', JSON.stringify(consoleLogs, null, 2));

    await browser.close();
})();
