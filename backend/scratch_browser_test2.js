const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const page = await context.newPage();

    page.on('console', msg => {
        console.log('[BROWSER CONSOLE]', msg.text());
    });

    // Inject token before loading
    await page.addInitScript(() => {
        // Create token for admin
        localStorage.setItem('auth_token', 'test_token');
        localStorage.setItem('user', JSON.stringify({ username: 'admin', role: 'admin' }));
    });

    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 20000 }).catch(e => console.log('goto err:', e.message));
    await page.waitForTimeout(2000);

    // Let's find links or navigate to runs
    console.log('Current URL:', page.url());
    await page.screenshot({ path: 'test_current_page.png' });

    await browser.close();
})();
