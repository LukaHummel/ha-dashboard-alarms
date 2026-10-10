/* Actual custom element in headless Chromium; mocked Home Assistant transport. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname,'..');
const fixture = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{margin:0;padding:12px;font-family:Arial;--primary-color:#3975a9;--primary-text-color:#e8eaed;--secondary-text-color:#b3b6bd;--secondary-background-color:#30343b;--card-background-color:#202329;--divider-color:#4d5158;--error-color:#ff8b80;background:#16191e}
</style></head><body><script type="module">
import {DashboardAlarmsCard} from '/card.js';
window.calls=[];window.unsubscribes=0;window.fail=false;window.delay=0;
window.connectionEvents={};window.handlers=[];
window.data={time_zone:'Europe/Berlin',defaults:{},alarms:[]};
window.connection={
 addEventListener:(name,handler)=>window.connectionEvents[name]=handler,
 removeEventListener:(name,handler)=>{if(window.connectionEvents[name]===handler)delete window.connectionEvents[name]},
 subscribeMessage:async callback=>{window.callback=callback;window.handlers.push(callback);callback(window.data);return()=>window.unsubscribes++}
};
window.hass={connection:window.connection,config:{time_zone:'Europe/Berlin'},locale:{language:'en-GB',time_format:'24'},
 states:{'calendar.alarms':{entity_id:'calendar.alarms',state:'off',attributes:{dashboard_alarms:true,friendly_name:'Alarms'}},
 'media_player.kitchen':{entity_id:'media_player.kitchen',state:'idle',attributes:{friendly_name:'Kitchen'}}},
 callWS:async command=>{window.calls.push(command);await new Promise(resolve=>setTimeout(resolve,window.delay));if(window.fail)throw new Error('Simulated save failure');
 if(command.command==='set_enabled'){window.data.alarms.find(alarm=>alarm.uid===command.uid).enabled=command.alarm.enabled;window.callback(window.data)}
 return{uid:command.uid||'new'};}
};
window.makeAlarms=count=>Array.from({length:count},(_,i)=>({uid:'alarm-'+i,name:'Alarm '+String(7+i%12).padStart(2,'0')+':00 - Daily',
 start:'2026-10-12T'+String(7+i%12).padStart(2,'0')+':00:00+02:00',local_start:'2026-10-12T'+String(7+i%12).padStart(2,'0')+':00:00',
 repeat:'daily',weekdays:[],enabled:true,next_occurrence:'2026-10-12T'+String(7+i%12).padStart(2,'0')+':00:00+02:00',audio:{},state:'scheduled'}));
window.push=count=>{window.data.alarms=window.makeAlarms(count);window.callback(window.data)};
window.card=new DashboardAlarmsCard();card.setConfig({type:'custom:dashboard-alarms-card',entity:'calendar.alarms'});card.hass=window.hass;document.body.append(card);
</script></body></html>`;

(async()=>{
  const server=http.createServer((request,response)=>{
    if(request.url==='/card.js'){response.setHeader('Content-Type','text/javascript');response.end(fs.readFileSync(path.join(root,'custom_components/dashboard_alarms/frontend/dashboard-alarms-card.js')))}
    else{response.setHeader('Content-Type','text/html');response.end(fixture)}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try{
    browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_EXECUTABLE} : {})});
    const page=await browser.newPage({viewport:{width:1280,height:800}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(()=>window.callback);
    await page.getByText('No alarms yet.').waitFor();
    await page.evaluate(()=>push(3));
    const rectangles=await page.locator('.tile').evaluateAll(nodes=>nodes.map(node=>({x:node.getBoundingClientRect().x,width:node.getBoundingClientRect().width})));
    assert.equal(new Set(rectangles.map(rect=>rect.x)).size,3,'three columns use tablet width');
    assert(rectangles.every(rect=>rect.width>350));
    await page.getByRole('switch').first().click();
    await page.waitForFunction(()=>card.shadowRoot.querySelector('[role=switch]').getAttribute('aria-checked')==='false');
    assert.equal(await page.getByRole('switch').first().getAttribute('aria-checked'),'false');
    assert.equal(await page.evaluate(()=>calls.at(-1).command),'set_enabled');
    await page.getByRole('button',{name:'New alarm'}).click();
    await page.locator('#repeat').selectOption('weekdays');
    await page.getByRole('button',{name:'Save alarm',exact:true}).click();
    await page.getByText('Select at least one weekday.').waitFor();
    await page.getByRole('button',{name:'Mon',exact:true}).click();
    await page.evaluate(()=>{window.fail=true;window.calls=[]});
    await page.getByRole('button',{name:'Save alarm',exact:true}).click();
    await page.getByText('Simulated save failure').waitFor();
    assert.equal(await page.locator('dialog[open]').count(),1,'failed save keeps editor open');
    await page.evaluate(()=>{window.fail=false;window.delay=150;window.calls=[];card._saveDialog();card._saveDialog()});
    await page.waitForFunction(()=>!card._dialog);
    assert.equal(await page.evaluate(()=>calls.length),1,'double save produces one command');
    assert.deepEqual(await page.evaluate(()=>calls[0].alarm.weekdays),[0]);
    await page.evaluate(()=>{data.alarms[0].state='ringing';data.alarms[0].enabled=true;callback(data)});
    await page.getByRole('button',{name:'Snooze',exact:true}).click();
    assert.equal(await page.evaluate(()=>calls.at(-1).command),'snooze');
    await page.getByRole('button',{name:'Dismiss',exact:true}).click();
    assert.equal(await page.evaluate(()=>calls.at(-1).command),'dismiss');
    await page.evaluate(()=>{data.alarms[0].state='scheduled';callback(data)});
    await page.getByRole('button',{name:'Edit alarm',exact:true}).first().click();
    page.once('dialog',dialog=>dialog.dismiss());
    await page.getByRole('button',{name:'Delete',exact:true}).click();
    assert.equal(await page.locator('dialog[open]').count(),1,'cancelled deletion retains editor');
    page.once('dialog',dialog=>dialog.accept());
    await page.getByRole('button',{name:'Delete',exact:true}).click();
    await page.waitForFunction(()=>!card._dialog);
    assert.equal(await page.evaluate(()=>calls.at(-1).command),'delete_alarm');
    await page.evaluate(()=>{window.connectionEvents.ready()});
    await page.waitForFunction(()=>window.handlers.length===2);
    assert.equal(await page.evaluate(()=>unsubscribes),1);
    await page.evaluate(()=>card.setConfig({entity:'calendar.alarms',max_height:320}));
    await page.evaluate(()=>push(20));
    const scroll=await page.locator('#tiles').evaluate(node=>({client:node.clientHeight,scroll:node.scrollHeight}));
    assert(scroll.scroll>scroll.client);
    await page.locator('#tiles').evaluate(node=>node.scrollTop=node.scrollHeight);
    assert(await page.locator('.tile').last().isVisible());
    assert(await page.locator('#tiles').evaluate(node=>node.lastElementChild.getBoundingClientRect().bottom<=node.getBoundingClientRect().bottom));
    fs.mkdirSync(path.join(root,'outputs/previews'),{recursive:true});
    await page.evaluate(()=>{card.setConfig({entity:'calendar.alarms'});push(6)});
    await page.locator('#tiles').evaluate(node=>node.scrollTop=0);
    await page.screenshot({path:path.join(root,'outputs/previews/tablet.png'),fullPage:true});
    await page.setViewportSize({width:360,height:800});
    const mobile=await page.locator('.tile').evaluateAll(nodes=>nodes.map(node=>node.getBoundingClientRect().x));
    assert.equal(new Set(mobile).size,1,'phone uses one column');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=360),'no horizontal overflow');
    await page.getByRole('button',{name:'New alarm'}).click();
    await page.locator('#repeat').selectOption('weekdays');
    const touch=await page.locator('dialog button:visible').evaluateAll(nodes=>nodes.map(node=>({width:node.getBoundingClientRect().width,height:node.getBoundingClientRect().height})));
    assert(touch.every(rect=>rect.width>=44 && rect.height>=44),'touch targets are at least 44px');
    await page.screenshot({path:path.join(root,'outputs/previews/phone-editor.png'),fullPage:true});
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await page.evaluate(()=>{hass.locale.time_format='12';card.hass=hass});
    await page.getByRole('button',{name:'New alarm'}).click();
    assert(await page.locator('#ampm').isVisible());
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await page.evaluate(()=>card.remove());
    assert.equal(await page.evaluate(()=>Object.keys(connectionEvents).length),0,'connection listeners removed');
    assert.equal(await page.evaluate(()=>unsubscribes),2,'subscription removed');
    assert.deepEqual(errors,[]);
    console.log('Card browser checks passed: responsive tiles, toggles, editor validation, error recovery, duplicate-save guard, snooze/dismiss, delete confirmation, reconnect and teardown.');
  }finally{
    await browser?.close();await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1});
