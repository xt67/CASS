import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const browser = await chromium.launch({channel:'chrome', headless:true});
try {
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://127.0.0.1:3000');
  await page.locator('#sql-input').fill('SELECT COUNT(*) AS customer_count FROM customers');
  await page.locator('#btn-run').click();
  await page.locator('#table-body').getByText('20',{exact:true}).waitFor();
  await mkdir('../docs/screenshots',{recursive:true});
  await page.screenshot({path:'../docs/screenshots/release-query.png',fullPage:true});
  console.log('CASS query UI verified; screenshot saved');
  await page.goto('http://127.0.0.1:8502');
  await page.getByText('US AQI · current-hour estimate',{exact:true}).waitFor({timeout:60000});
  await page.getByText('Missing provider values remain unavailable;', {exact:false}).waitFor({timeout:60000});
  if (await page.locator('[data-testid="stException"]').count()) throw new Error('PAQS Streamlit exception');
  await page.waitForFunction(() => document.querySelectorAll('[data-testid=stSkeleton]').length === 0, {timeout:60000});
  const paqs=path.resolve('../../pune-air-quality-sentinel/docs/screenshots/live-api.png');
  await page.screenshot({path:paqs,fullPage:true});
  console.log('PAQS live UI verified; screenshot saved');
  await page.goto('http://127.0.0.1:8503');
  await page.getByText('ML-Based Autonomous Driving',{exact:false}).first().waitFor({timeout:60000});
  await page.getByRole('tab',{name:/3D View/}).click();
  await page.getByText('Illustrative DQN Q-Network',{exact:false}).waitFor({timeout:30000});
  if (await page.locator('[data-testid="stException"]').count()) throw new Error('AutoCar Streamlit exception');
  await page.getByRole('tab',{name:/Training/}).click();
  await page.screenshot({path:path.resolve('../../../docs/images/release-dashboard.png'),fullPage:true});
  console.log('AutoCar dashboard verified; screenshot saved');
  if(errors.length) throw new Error(errors.join('\n'));
} finally {
  await browser.close();
}
