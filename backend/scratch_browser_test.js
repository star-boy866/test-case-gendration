
const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const page = await context.newPage();

    page.on('console', msg => {
        const text = msg.text();
        if (text.includes('PREVIEW') || text.includes('EDITOR') || text.includes('SOURCE IMAGE IDENTITY') || text.includes('SOURCE SNAPSHOT EDITOR INIT')) {
            console.log('[BROWSER CONSOLE]', text);
        }
    });

    await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 15000 }).catch(e => console.log('goto err:', e.message));
    console.log('Page title:', await page.title());

    // Check if we are on login or cognos page
    const content = await page.content();
    console.log('Page loaded, HTML length:', content.length);

    await browser.close();
})();
