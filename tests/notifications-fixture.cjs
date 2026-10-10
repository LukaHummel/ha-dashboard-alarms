/* Shared mocked Home Assistant shell for browser regression tests and previews. */
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const fixture = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{margin:0;background:#f6f7f9;font:16px Arial;color:#202124}home-assistant{display:block;--primary-color:#3975a9;--card-background-color:#fff;--secondary-background-color:#edf1f5;--divider-color:#e0e4e8;--primary-text-color:#202124;--secondary-text-color:#62656a}
header{background:#3975a9;color:#fff;padding:20px 24px;font-size:22px}main{padding:32px;max-width:1000px;margin:auto}.setting{background:#fff;padding:24px;border:1px solid #ddd;border-radius:12px;margin:16px 0}h1{font-size:28px}
</style></head><body><home-assistant><header>Home Assistant</header><main><h1>Settings</h1><p>The alarm dashboard is not mounted in this view.</p><div class="setting">Devices & services</div><div class="setting">Dashboards</div><div class="setting">System</div></main></home-assistant>
<script>
customElements.define('home-assistant', class extends HTMLElement {});
window.calls=[];window.fail=false;window.delay=0;window.unsubscribes=0;window.subscriptionDelay=0;
window.snapshots={
  'calendar.alarms':{can_control:true,time_zone:'Europe/Berlin',defaults:{snooze_minutes:10},alarms:[]},
  'calendar.other':{can_control:true,time_zone:'Europe/Berlin',defaults:{snooze_minutes:5},alarms:[]}
};
window.callbacks=new Map();window.events=new Map();
window.emit=(name)=>{for(const handler of [...(events.get(name)||[])])handler()};
window.connection={connected:true,
 addEventListener:(name,handler)=>{if(!events.has(name))events.set(name,new Set());events.get(name).add(handler)},
 removeEventListener:(name,handler)=>events.get(name)?.delete(handler),
 subscribeMessage:async (callback,msg)=>{
  if(!callbacks.has(msg.entity_id))callbacks.set(msg.entity_id,new Set());callbacks.get(msg.entity_id).add(callback);
  if(subscriptionDelay)await new Promise(resolve=>setTimeout(resolve,subscriptionDelay));
  callback(snapshots[msg.entity_id]);
  return()=>{callbacks.get(msg.entity_id).delete(callback);unsubscribes++};
 }
};
window.hass={connection,config:{time_zone:'Europe/Berlin'},locale:{language:'en-GB',time_format:'24'},
 states:Object.fromEntries(Object.keys(snapshots).map(entity_id=>[entity_id,{entity_id,state:'off',attributes:{dashboard_alarms:true}}])),
 callWS:async command=>{
  calls.push(command);await new Promise(resolve=>setTimeout(resolve,delay));if(fail)throw new Error('Simulated connection failure');
  const alarm=snapshots[command.entity_id].alarms.find(alarm=>alarm.uid===command.uid);
  alarm.state=command.command==='snooze'?'snoozed':'dismissed';
  if(command.command==='dismiss'&&alarm.repeat==='once')alarm.enabled=false;
  publish(command.entity_id);return{uid:command.uid};
 }
};
document.querySelector('home-assistant').hass=hass;
window.publish=entityId=>{for(const callback of [...(callbacks.get(entityId)||[])])callback(structuredClone(snapshots[entityId]))};
window.ring=(entityId='calendar.alarms',uid='one',extra={})=>{
 snapshots[entityId].alarms=[{uid,name:'Alarm 07:00',start:'2026-10-12T07:00:00+02:00',
 ring_started:'2026-10-12T07:00:00+02:00',repeat:'once',enabled:true,state:'ringing',audio:{},...extra}];publish(entityId);
};
</script><script type="module" src="/dashboard-alarms-notifications.js"></script></body></html>`;

function createServer() {
  return http.createServer((request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    if (pathname === '/dashboard-alarms-notifications.js') {
      response.setHeader('Content-Type', 'text/javascript');
      response.end(fs.readFileSync(path.join(root, 'custom_components/dashboard_alarms/frontend/dashboard-alarms-notifications.js')));
    } else {
      response.setHeader('Content-Type', 'text/html');
      response.end(fixture);
    }
  });
}

module.exports = {createServer};
if (require.main === module) {
  createServer().listen(8124, '127.0.0.1', () => console.log('Alarm dialog preview: http://127.0.0.1:8124'));
}
