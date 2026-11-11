import { chromium } from '@playwright/test';
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.on('console',m=> { if(m.type()==='error') console.log('CONSOLE',m.text()); });
page.on('requestfailed',r=>console.log('FAILED',r.url(),r.failure()?.errorText));
await page.goto('http://127.0.0.1:8502');
await page.getByText('Missing provider values remain unavailable;', {exact:false}).waitFor({timeout:60000});
await page.waitForFunction(() => document.querySelectorAll('[data-testid=stSkeleton]').length === 0, {timeout:60000});
console.log(await page.locator('[data-testid]').evaluateAll(nodes=>[...new Set(nodes.map(n=>n.dataset.testid))]));
console.log('canvas',await page.locator('canvas').count(),'svg',await page.locator('svg').count());
await page.screenshot({path:'../../pune-air-quality-sentinel/docs/screenshots/live-api.png',fullPage:true});
} finally {await browser.close();}
