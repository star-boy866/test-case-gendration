const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const page = await context.newPage();

    const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvYnVsaSIsInJvbGUiOiJhZG1pbiIsImlhdCI6MTc4NzY1OTU1OCwiZXhwIjoxNzg3Njg4MzU4fQ.BZpmQP129UH6xhY6dXSBwXPIPBtNb0oitQeeCbQmO8o';

    await page.addInitScript((tok) => {
        localStorage.setItem('healthcare_nl_testgen_token', tok);
        localStorage.setItem('user', JSON.stringify({ id: 1, username: 'obuli', role: 'admin' }));
    }, token);

    await page.goto('http://localhost:5173/cognos', { waitUntil: 'networkidle', timeout: 15000 });
    await page.click('button:has-text("Execution Scenarios")');
    await page.waitForTimeout(2000);

    const rhdrBtn = await page.$('tr:has-text("OPR188-RHDR-01"), td:has-text("OPR188-RHDR-01")');
    if (rhdrBtn) {
        await rhdrBtn.click();
        await page.waitForTimeout(3000);
    }

    // Scroll down to DSD Evidence section
    const dsdEvidenceHeader = await page.$('text=DSD Evidence');
    if (dsdEvidenceHeader) {
        await dsdEvidenceHeader.scrollIntoViewIfNeeded();
        await page.waitForTimeout(2000);
    }

    await page.screenshot({ path: 'test_rhdr_scrolled_card.png' });
    console.log('Saved test_rhdr_scrolled_card.png');

    await browser.close();
})();
