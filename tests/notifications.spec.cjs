/* Ringing controls must outlive cards and remain usable across HA panels. */
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const {createServer} = require('./notifications-fixture.cjs');

(async () => {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true,
      ...(process.env.PLAYWRIGHT_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_EXECUTABLE} : {})});
    const page = await browser.newPage({viewport:{width:1280, height:800}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => callbacks.size === 2);
    assert.equal(await page.locator('dashboard-alarms-card').count(), 0, 'no dashboard card is mounted');
    assert.equal(await page.locator('dialog[open]').count(), 0);
    await page.evaluate(() => ring());
    await page.getByRole('dialog', {name:'Alarm ringing', exact:true}).waitFor();
    const buttons = page.getByRole('dialog').getByRole('button');
    const sizes = await buttons.evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
    assert(sizes.every(height => height >= 100), 'desktop controls are large');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('dialog[open]').count(), 1, 'Escape cannot hide ringing');
    await page.evaluate(() => {fail=true});
    await page.getByRole('button', {name:'Dismiss Stop this alarm', exact:true}).click();
    await page.getByText('Simulated connection failure').waitFor();
    assert.equal(await page.locator('dialog[open]').count(), 1, 'failed command keeps modal open');
    await page.evaluate(() => {fail=false;delay=150;calls=[];dashboardAlarmsNotifications._command('calendar.alarms:one','snooze');dashboardAlarmsNotifications._command('calendar.alarms:one','snooze')});
    await page.waitForFunction(() => !dashboardAlarmsNotifications._dialog.open);
    assert.equal(await page.evaluate(() => calls.length), 1, 'duplicate actions are blocked');
    assert.deepEqual(await page.evaluate(() => calls[0]), {
      type:'dashboard_alarms/command', entity_id:'calendar.alarms', uid:'one', command:'snooze',
    });
    await page.evaluate(() => {delay=0;ring();ring('calendar.other','one',{name:'Other calendar alarm',audio:{snooze_minutes:7}})});
    await page.getByRole('dialog', {name:'Alarms ringing', exact:true}).waitFor();
    assert.equal(await page.getByRole('dialog').locator('article').count(), 2);
    await page.evaluate(() => emit('disconnected'));
    await page.getByText('Home Assistant disconnected. Reconnecting…').waitFor();
    assert(await page.getByRole('dialog').getByRole('button').first().isDisabled());
    await page.evaluate(() => emit('ready'));
    await page.waitForFunction(() => [...callbacks.values()].every(set => set.size === 1));
    assert.equal(await page.evaluate(() => unsubscribes), 2);
    assert(await page.getByRole('dialog').getByRole('button').first().isEnabled());
    await page.getByRole('dialog').locator('article').first().getByRole('button', {name:'Dismiss Stop this alarm', exact:true}).click();
    await page.waitForFunction(() => snapshots['calendar.alarms'].alarms[0].enabled === false);
    assert.equal(await page.locator('dialog[open]').count(), 1, 'remaining calendar keeps modal open');
    assert.equal(await page.getByRole('dialog').locator('article').count(), 1);
    await page.setViewportSize({width:360, height:800});
    const mobile = await page.getByRole('dialog').getByRole('button').evaluateAll(nodes => nodes.map(node => ({
      height:node.getBoundingClientRect().height, x:node.getBoundingClientRect().x,
    })));
    assert(mobile.every(button => button.height >= 96));
    assert.equal(new Set(mobile.map(button => button.x)).size, 1, 'phone controls stack');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= 360));
    await page.getByRole('button', {name:'Snooze 7 minutes', exact:true}).click();
    await page.waitForFunction(() => !dashboardAlarmsNotifications._dialog.open);
    assert.equal(await page.evaluate(() => calls.at(-1).entity_id), 'calendar.other');
    await page.evaluate(() => ring('calendar.alarms','html',{name:'<img src=x onerror=alert(1)>',audio_error:'<script>bad()</script>'}));
    assert.equal(await page.getByRole('dialog').locator('img,script').count(), 0, 'alarm content is escaped');
    await page.evaluate(() => {delete hass.states['calendar.alarms'];dashboardAlarmsNotifications._syncHass()});
    await page.waitForFunction(() => !dashboardAlarmsNotifications._dialog.open);
    // A subscription resolving after its entity is removed must be unsubscribed
    // and must not reopen the dialog with its stale ringing snapshot.
    await page.evaluate(() => {
      subscriptionDelay=100;
      hass.states['calendar.alarms']={entity_id:'calendar.alarms',state:'off',attributes:{dashboard_alarms:true}};
      dashboardAlarmsNotifications._syncHass();
      delete hass.states['calendar.alarms'];
      dashboardAlarmsNotifications._syncHass();
    });
    await page.waitForFunction(() => callbacks.get('calendar.alarms').size === 0);
    assert.equal(await page.locator('dialog[open]').count(), 0, 'late snapshot cannot reopen modal');
    await page.evaluate(() => {
      subscriptionDelay=0;ring('calendar.other');
      snapshots['calendar.other'].alarms[0].state='timed_out';publish('calendar.other');
    });
    assert.equal(await page.locator('dialog[open]').count(), 0, 'timeout closes the modal');
    await page.evaluate(() => {
      snapshots['calendar.other'].can_control=false;ring('calendar.other');
    });
    assert.equal(await page.locator('dialog[open]').count(), 0, 'read-only users are not blocked by controls they cannot use');
    await page.evaluate(() => dashboardAlarmsNotifications.remove());
    assert.equal(await page.evaluate(() => [...events.values()].reduce((sum,set)=>sum+set.size,0)), 0);
    assert.equal(await page.evaluate(() => [...callbacks.values()].reduce((sum,set)=>sum+set.size,0)), 0);
    assert.deepEqual(errors, []);
    console.log('Global alarm dialog checks passed: no mounted card, large controls, failures, duplicate actions, multiple calendars, reconnect, mobile layout, escaping, and cleanup.');
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => {console.error(error);process.exitCode=1});
