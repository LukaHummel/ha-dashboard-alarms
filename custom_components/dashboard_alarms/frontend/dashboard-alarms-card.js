/* Dashboard Alarms — local, dependency-free dashboard card. */
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const style = `
  :host { display:block; font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif); color:var(--primary-text-color,#202124); }
  * { box-sizing:border-box; } button,input,select,textarea { font:inherit; }
  button { cursor:pointer; min-height:44px; min-width:44px; border:0; border-radius:10px; padding:8px 14px; background:var(--secondary-background-color,#eceff3); color:inherit; }
  button:disabled { cursor:wait; opacity:.55; } button:focus-visible,input:focus-visible,select:focus-visible { outline:3px solid var(--primary-color,#3975a9); outline-offset:2px; }
  .primary { background:var(--primary-color,#3975a9); color:var(--text-primary-color,white); } .danger { color:var(--error-color,#b33b36); }
  ha-card { display:block; background:var(--ha-card-background,var(--card-background-color,#fff)); border-radius:var(--ha-card-border-radius,12px); border:1px solid var(--ha-card-border-color,var(--divider-color,#ddd)); overflow:hidden; }
  header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 16px; }
  h2 { font-size:22px; line-height:1.25; margin:0; overflow-wrap:anywhere; } header button { flex-shrink:0; }
  .tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr)); gap:12px; padding:0 12px 16px; align-content:start; overflow:auto; }
  .tile { padding:14px; border:1px solid var(--divider-color,#ddd); border-radius:12px; background:var(--secondary-background-color,#f5f6f8); min-width:0; }
  .tile.disabled { opacity:.72; } .tile.ringing { border:2px solid var(--primary-color,#3975a9); }
  .top { display:flex; justify-content:space-between; align-items:center; gap:8px; } .time { font-size:30px; font-weight:600; line-height:1.2; }
  .name { font-size:16px; font-weight:600; margin:8px 0 4px; overflow-wrap:anywhere; } .detail { font-size:14px; line-height:1.5; color:var(--secondary-text-color,#62656a); overflow-wrap:anywhere; }
  .actions { display:flex; justify-content:center; align-items:center; gap:8px; margin-top:12px; } .actions button { flex:1; max-width:160px; }
  .tile.ringing .actions button { min-height:72px; font-size:20px; max-width:none; }
  .switch { width:52px; min-width:52px; position:relative; background:transparent; padding:0; } .track { display:block; width:40px; height:24px; border-radius:14px; margin:auto; background:var(--disabled-color,#9a9da2); }
  .switch[aria-checked=true] .track { background:var(--primary-color,#3975a9); } .track:after { content:''; display:block; width:18px; height:18px; border-radius:50%; background:white; position:relative; top:3px; left:3px; transition:transform .15s; }
  .switch[aria-checked=true] .track:after { transform:translateX(16px); }
  .error { color:var(--error-color,#b33b36); padding:8px 16px; overflow-wrap:anywhere; font-size:14px; } .empty { grid-column:1/-1; padding:24px; text-align:center; color:var(--secondary-text-color,#62656a); }
  dialog { width:min(560px,calc(100vw - 24px)); max-height:calc(100dvh - 24px); padding:0; border:1px solid var(--divider-color,#ddd); border-radius:16px; color:inherit; background:var(--ha-card-background,var(--card-background-color,#fff)); }
  dialog::backdrop { background:rgba(0,0,0,.55); } .dialog-head { display:flex; justify-content:space-between; align-items:center; padding:12px 16px; }
  .form { padding:0 16px 16px; overflow:auto; max-height:calc(100dvh - 175px); } label,.label { display:block; margin:12px 0 6px; font-size:14px; }
  input,select,textarea { width:100%; min-height:44px; border:1px solid var(--divider-color,#bbb); border-radius:8px; padding:10px; color:inherit; background:var(--secondary-background-color,#f5f6f8); }
  .clock { display:flex; justify-content:center; align-items:center; gap:12px; margin:12px 0; } .clock-col { display:grid; justify-items:center; gap:6px; } .clock-col button { width:64px; } .clock-col output { font-size:40px; font-variant-numeric:tabular-nums; } .colon { font-size:40px; }
  .weekdays { display:grid; grid-template-columns:repeat(auto-fit,minmax(44px,1fr)); gap:4px; margin-top:12px; } .weekdays button { padding:4px; min-width:44px; min-height:48px; } .weekdays button[aria-pressed=true] { background:var(--primary-color,#3975a9); color:var(--text-primary-color,white); }
  .footer { display:flex; justify-content:space-between; align-items:center; gap:8px; padding:12px 16px; border-top:1px solid var(--divider-color,#ddd); } .footer-right { display:flex; gap:8px; margin-left:auto; }
  details { margin-top:16px; } summary { cursor:pointer; min-height:44px; display:flex; align-items:center; } .checkbox { display:flex; align-items:center; gap:8px; min-height:44px; margin:0; } .checkbox input { width:22px; min-height:22px; height:22px; }
  [hidden] { display:none!important; } .hint { font-size:13px; color:var(--secondary-text-color,#62656a); line-height:1.4; }
  @media(max-width:380px) { header { padding:12px; } h2 { font-size:19px; } .weekdays { grid-template-columns:repeat(4,1fr); } .footer { padding:8px; } }
`;

export function repeatLabel(alarm) {
  return alarm.repeat === 'daily' ? 'Daily' : alarm.repeat === 'weekdays'
    ? (alarm.weekdays || []).map(day => labels[day]).join(', ') : 'Once';
}

export function localParts(date, zone) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone:zone, year:'numeric', month:'2-digit', day:'2-digit',
    hour:'2-digit', minute:'2-digit', hourCycle:'h23'
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return { date:`${values.year}-${values.month}-${values.day}`, hour:Number(values.hour), minute:Number(values.minute) };
}

export class DashboardAlarmsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._generation = 0;
    this._busy = new Set();
    this._data = {alarms:[]};
    this._ready = () => this._restartSubscription();
    this._offline = () => { this._error = 'Home Assistant disconnected. Reconnecting…'; this._renderTiles(); };
  }

  setConfig(config) {
    if (!config.entity || !config.entity.startsWith('calendar.')) throw new Error('Select a Dashboard Alarms calendar entity.');
    if (config.max_height !== undefined && (!Number.isFinite(Number(config.max_height)) || Number(config.max_height) < 120))
      throw new Error('Maximum height must be a number of at least 120 pixels.');
    const changed = this._config?.entity !== config.entity;
    this._config = {...config};
    if (changed) { this._data = {alarms:[]}; this._closeDialog(); this._stopSubscription(); }
    this._render();
    this._subscribe();
  }

  set hass(hass) {
    const changed = this._hass?.connection !== hass.connection;
    const oldState = this._hass?.states?.[this._config?.entity]?.state;
    if (changed) { this._detachConnection(); this._stopSubscription(); }
    this._hass = hass;
    if (this.isConnected) this._attachConnection();
    const state = hass.states?.[this._config?.entity]?.state;
    if ((oldState === 'unavailable' || this._wasAbsent) && state && state !== 'unavailable') this._restartSubscription();
    else this._subscribe();
    this._wasAbsent = !state;
    this._renderTiles();
  }

  connectedCallback() { this._attachConnection(); this._subscribe(); }
  disconnectedCallback() { this._stopSubscription(); this._detachConnection(); this._closeDialog(); }
  _attachConnection() {
    const connection = this._hass?.connection;
    if (!connection || connection === this._connection) return;
    this._connection = connection;
    connection.addEventListener('ready',this._ready);
    connection.addEventListener('disconnected',this._offline);
  }
  _detachConnection() {
    this._connection?.removeEventListener('ready',this._ready);
    this._connection?.removeEventListener('disconnected',this._offline);
    this._connection = null;
  }
  _stopSubscription() {
    this._generation++;
    this._subscribing = false;
    this._unsubscribe?.(); this._unsubscribe = null;
    clearTimeout(this._retry);
  }
  _restartSubscription() { this._stopSubscription(); this._subscribe(); }

  async _subscribe() {
    if (!this.isConnected || !this._hass || !this._config || this._unsubscribe || this._subscribing) return;
    this._subscribing = true;
    const generation = this._generation;
    try {
      const unsubscribe = await this._hass.connection.subscribeMessage(data => {
        if (generation !== this._generation) return;
        this._data = data; this._error = ''; this._renderTiles();
      }, {type:'dashboard_alarms/subscribe',entity_id:this._config.entity});
      if (generation !== this._generation || !this.isConnected) unsubscribe();
      else { this._unsubscribe = unsubscribe; this._renderTiles(); }
    } catch (error) {
      if (generation !== this._generation) return;
      this._error = error.message || String(error); this._renderTiles();
      this._retry = setTimeout(() => this._subscribe(),5000);
    } finally {
      if (generation === this._generation) this._subscribing = false;
    }
  }

  _hour12() {
    const format = this._hass?.locale?.time_format;
    if (format === '12') return true;
    if (format === '24') return false;
    return new Intl.DateTimeFormat(this._hass?.locale?.language || navigator.language,{hour:'numeric'}).resolvedOptions().hour12;
  }
  _format(value, date=false) {
    if (!value) return 'No upcoming occurrence';
    const options = {timeZone:this._data.time_zone || this._hass?.config?.time_zone, hour:'numeric',minute:'2-digit',hour12:this._hour12()};
    if (date) Object.assign(options,{month:'short',day:'numeric'});
    return new Intl.DateTimeFormat(this._hass?.locale?.language || navigator.language,options).format(new Date(value));
  }
  _render() {
    if (!this._config) return;
    this.shadowRoot.innerHTML = `<style>${style}</style><ha-card>
      <header><h2>${escapeHTML(this._config.title || 'Alarms')}</h2><button class="primary" id="new">＋ New alarm</button></header>
      <div id="error" class="error" role="alert" hidden></div><div class="tiles" id="tiles"></div>
    </ha-card>`;
    this.shadowRoot.getElementById('new').onclick = () => this._openDialog();
    this._renderTiles();
  }
  _renderTiles() {
    const tiles = this.shadowRoot.getElementById('tiles');
    if (!tiles) return;
    tiles.style.maxHeight = this._config.max_height ? `${Number(this._config.max_height)}px` : '';
    const error = this.shadowRoot.getElementById('error');
    error.hidden = !this._error; error.textContent = this._error || '';
    if (!this._data.alarms?.length) {
      tiles.innerHTML = `<div class="empty">${this._unsubscribe ? 'No alarms yet. Tap New alarm to create one.' : 'Connecting to the alarm calendar…'}</div>`;
      return;
    }
    tiles.innerHTML = this._data.alarms.map(alarm => {
      const busy = this._busy.has(alarm.uid) ? 'disabled' : '';
      const ringing = alarm.state === 'ringing';
      const time = this._format(alarm.start);
      const status = !alarm.enabled ? 'Disabled' : alarm.state === 'snoozed'
        ? `Snoozed until ${this._format(alarm.snooze_until,true)}` : ringing ? 'Ringing'
        : alarm.next_occurrence ? `Next: ${this._format(alarm.next_occurrence,true)}` : 'Completed';
      return `<article class="tile ${!alarm.enabled ? 'disabled' : ''} ${ringing ? 'ringing' : ''}" data-uid="${escapeHTML(alarm.uid)}">
        <div class="top"><span class="time">${escapeHTML(time)}</span>
          <button class="switch" role="switch" aria-checked="${alarm.enabled}" aria-label="Enable ${escapeHTML(alarm.name)}" data-action="toggle" ${busy}><span class="track"></span></button></div>
        <div class="name">${escapeHTML(alarm.name)}</div><div class="detail">${escapeHTML(repeatLabel(alarm))} · ${escapeHTML(status)}</div>
        ${alarm.last_missed ? `<div class="detail">Missed: ${escapeHTML(this._format(alarm.last_missed,true))}</div>` : ''}
        ${alarm.state === 'timed_out' ? '<div class="detail">Sound stopped at the time limit</div>' : ''}
        ${alarm.audio_error ? `<div class="error" role="status">${escapeHTML(alarm.audio_error)}</div>` : ''}
        <div class="actions">${ringing ? `<button data-action="snooze" class="primary" ${busy}>Snooze</button><button data-action="dismiss" ${busy}>Dismiss</button>`
          : alarm.state === 'snoozed' ? `<button data-action="dismiss" ${busy}>Dismiss snooze</button><button data-action="edit" ${busy}>Edit</button>`
          : `<button data-action="edit" ${busy}>Edit alarm</button>`}</div></article>`;
    }).join('');
    tiles.querySelectorAll('[data-action]').forEach(button => button.onclick = () => {
      const alarm = this._data.alarms.find(item => item.uid === button.closest('[data-uid]').dataset.uid);
      if (button.dataset.action === 'edit') this._openDialog(alarm);
      else if (button.dataset.action === 'toggle') this._tileCommand(alarm,'set_enabled',{alarm:{enabled:!alarm.enabled}});
      else this._tileCommand(alarm,button.dataset.action);
    });
  }
  async _command(command,extra={}) {
    return this._hass.callWS({type:'dashboard_alarms/command',entity_id:this._config.entity,command,...extra});
  }
  async _tileCommand(alarm,command,extra={}) {
    if (this._busy.has(alarm.uid)) return;
    this._busy.add(alarm.uid); this._renderTiles();
    try { await this._command(command,{uid:alarm.uid,...extra}); }
    catch (error) { this._error = error.message || String(error); }
    finally { this._busy.delete(alarm.uid); this._renderTiles(); }
  }

  _openDialog(alarm) {
    this._closeDialog();
    const zone = this._data.time_zone || this._hass.config.time_zone;
    const initial = alarm ? {
      date:alarm.local_start.slice(0,10),hour:Number(alarm.local_start.slice(11,13)),minute:Number(alarm.local_start.slice(14,16))
    } : localParts(new Date(Date.now()+3600000),zone);
    this._draft = {...initial, uid:alarm?.uid, repeat:alarm?.repeat || 'once', weekdays:[...(alarm?.weekdays || [])],
      enabled:alarm?.enabled ?? true, description:alarm?.description || '', audio:{...(alarm?.audio || {})}};
    const dialog = document.createElement('dialog');
    const audio = this._draft.audio;
    const players = Object.values(this._hass.states).filter(state => state.entity_id.startsWith('media_player.'));
    dialog.innerHTML = `<div class="dialog-head"><h2>${alarm ? 'Edit alarm' : 'New alarm'}</h2><button id="close" aria-label="Close alarm editor">✕</button></div>
      <div class="form"><div class="clock">
        <div class="clock-col"><button data-clock="hour:1" aria-label="Increase hour">＋</button><output id="hour" aria-label="Hour"></output><button data-clock="hour:-1" aria-label="Decrease hour">−</button></div>
        <span class="colon" aria-hidden="true">:</span>
        <div class="clock-col"><button data-clock="minute:1" aria-label="Increase minute">＋</button><output id="minute" aria-label="Minute"></output><button data-clock="minute:-1" aria-label="Decrease minute">−</button></div>
        <button id="ampm" aria-label="Switch AM or PM" ${this._hour12() ? '' : 'hidden'}></button></div>
        <label for="date">First alarm date</label><input id="date" type="date" value="${escapeHTML(initial.date)}" required>
        <label for="repeat">Repeat</label><select id="repeat"><option value="once">Once</option><option value="daily">Daily</option><option value="weekdays">Selected weekdays</option></select>
        <div class="weekdays" id="weekdays">${labels.map((label,index) => `<button data-day="${index}" aria-pressed="false">${label}</button>`).join('')}</div>
        <p class="hint">Times use ${escapeHTML(zone)}. Names are generated automatically.</p>
        ${alarm?.has_exceptions ? '<p class="hint">This series has calendar exceptions. Editing here updates the full schedule.</p>' : ''}
        <details><summary>Audio and description</summary>
          <label class="checkbox"><input id="inherit-targets" type="checkbox" ${audio.media_players === undefined ? 'checked' : ''}>Use default media players</label>
          <div id="targets">${players.map(player => `<label class="checkbox"><input type="checkbox" data-target="${escapeHTML(player.entity_id)}" ${audio.media_players?.includes(player.entity_id) ? 'checked' : ''}>${escapeHTML(player.attributes.friendly_name || player.entity_id)}</label>`).join('') || '<p class="hint">No media players found.</p>'}</div>
          <label for="sound">Sound URL or media-source URI (blank uses default)</label><input id="sound" value="${escapeHTML(audio.sound || '')}" placeholder="Default chime">
          <label for="snooze">Snooze minutes (blank uses default)</label><input id="snooze" type="number" min="1" max="120" value="${audio.snooze_minutes || ''}">
          <label for="ring">Maximum ring minutes (blank uses default)</label><input id="ring" type="number" min="1" max="120" value="${audio.ring_minutes || ''}">
          <label for="description">Description</label><textarea id="description" rows="2">${escapeHTML(this._draft.description)}</textarea>
        </details><div id="save-error" class="error" role="alert" hidden></div></div>
      <div class="footer"><button id="delete" class="danger" ${alarm ? '' : 'hidden'}>Delete</button><div class="footer-right"><button id="cancel">Cancel</button><button id="save" class="primary">Save alarm</button></div></div>`;
    this.shadowRoot.append(dialog); this._dialog = dialog;
    dialog.querySelector('#repeat').value = this._draft.repeat;
    dialog.querySelector('#repeat').onchange = event => { this._draft.repeat = event.target.value; this._updateWeekdays(); };
    dialog.querySelectorAll('[data-clock]').forEach(button => button.onclick = () => {
      const [key,amount] = button.dataset.clock.split(':');
      const limit = key === 'hour' ? 24 : 60;
      this._draft[key] = (this._draft[key]+Number(amount)+limit)%limit; this._updateClock();
    });
    dialog.querySelector('#ampm').onclick = () => { this._draft.hour = (this._draft.hour+12)%24; this._updateClock(); };
    dialog.querySelectorAll('[data-day]').forEach(button => button.onclick = () => {
      const day = Number(button.dataset.day);
      this._draft.weekdays = this._draft.weekdays.includes(day) ? this._draft.weekdays.filter(value => value !== day) : [...this._draft.weekdays,day].sort();
      this._updateWeekdays();
    });
    const updateTargets = () => { dialog.querySelector('#targets').hidden = dialog.querySelector('#inherit-targets').checked; };
    dialog.querySelector('#inherit-targets').onchange = updateTargets; updateTargets();
    for (const id of ['close','cancel']) dialog.querySelector(`#${id}`).onclick = () => this._closeDialog();
    dialog.addEventListener('cancel',event => { if (this._saving) event.preventDefault(); else this._closeDialog(); });
    dialog.querySelector('#save').onclick = () => this._saveDialog();
    dialog.querySelector('#delete').onclick = () => this._deleteDialog();
    this._updateClock(); this._updateWeekdays(); dialog.showModal();
  }
  _updateClock() {
    if (!this._dialog) return;
    this._dialog.querySelector('#hour').textContent = String(this._hour12() ? this._draft.hour%12 || 12 : this._draft.hour).padStart(2,'0');
    this._dialog.querySelector('#minute').textContent = String(this._draft.minute).padStart(2,'0');
    this._dialog.querySelector('#ampm').textContent = this._draft.hour < 12 ? 'AM' : 'PM';
  }
  _updateWeekdays() {
    this._dialog.querySelector('#weekdays').hidden = this._draft.repeat !== 'weekdays';
    this._dialog.querySelectorAll('[data-day]').forEach(button => button.setAttribute('aria-pressed',String(this._draft.weekdays.includes(Number(button.dataset.day)))));
  }
  _closeDialog() {
    if (this._saving) return;
    this._dialog?.close(); this._dialog?.remove(); this._dialog = null;
  }
  _dialogError(error) {
    const box = this._dialog?.querySelector('#save-error');
    if (box) { box.hidden = false; box.textContent = error.message || String(error); }
  }
  _setSaving(value) {
    this._saving = value;
    this._dialog?.querySelectorAll('button,input,select,textarea').forEach(element => element.disabled = value);
  }
  async _saveDialog() {
    if (this._saving) return;
    const dialog = this._dialog;
    const date = dialog.querySelector('#date').value;
    if (!date) { this._dialogError(new Error('Choose the first alarm date.')); return; }
    if (this._draft.repeat === 'weekdays' && !this._draft.weekdays.length) { this._dialogError(new Error('Select at least one weekday.')); return; }
    const audio = {};
    if (!dialog.querySelector('#inherit-targets').checked)
      audio.media_players = [...dialog.querySelectorAll('[data-target]:checked')].map(element => element.dataset.target);
    const sound = dialog.querySelector('#sound').value.trim(); if (sound) audio.sound = sound;
    for (const [id,key] of [['snooze','snooze_minutes'],['ring','ring_minutes']]) {
      const input = dialog.querySelector(`#${id}`);
      if (input.value) {
        if (!input.checkValidity()) { this._dialogError(new Error('Minutes must be a whole number from 1 to 120.')); return; }
        audio[key] = Number(input.value);
      }
    }
    const start = `${date}T${String(this._draft.hour).padStart(2,'0')}:${String(this._draft.minute).padStart(2,'0')}:00`;
    const alarm = {start,repeat:this._draft.repeat,weekdays:this._draft.weekdays,enabled:this._draft.enabled,
      description:dialog.querySelector('#description').value,audio};
    this._setSaving(true);
    try {
      await this._command(this._draft.uid ? 'update_alarm' : 'create_alarm',{...(this._draft.uid ? {uid:this._draft.uid} : {}),alarm});
      this._setSaving(false); this._closeDialog();
    } catch (error) { this._dialogError(error); this._setSaving(false); }
  }
  async _deleteDialog() {
    if (this._saving || !this._draft.uid || !window.confirm('Delete this alarm and its complete repeating schedule?')) return;
    this._setSaving(true);
    try {
      await this._command('delete_alarm',{uid:this._draft.uid});
      this._setSaving(false); this._closeDialog();
    } catch (error) { this._dialogError(error); this._setSaving(false); }
  }
  getCardSize() { return Math.max(2,Math.ceil((this._data.alarms?.length || 1)/2)*4); }
  getGridOptions() { return {columns:'full',min_columns:6,min_rows:2}; }
  static getConfigElement() { return document.createElement('dashboard-alarms-card-editor'); }
  static getStubConfig(hass) {
    return {entity:Object.values(hass.states).find(state => state.attributes.dashboard_alarms)?.entity_id || 'calendar.dashboard_alarms'};
  }
}

class DashboardAlarmsCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); }
  setConfig(config) { this._config = {...config}; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }
  _render() {
    if (!this._config || !this._hass) return;
    const entities = Object.values(this._hass.states).filter(state => state.attributes.dashboard_alarms);
    this.shadowRoot.innerHTML = `<style>${style}</style><label for="entity">Alarm calendar</label><select id="entity"><option value="">Choose a calendar</option>${entities.map(state => `<option value="${escapeHTML(state.entity_id)}">${escapeHTML(state.attributes.friendly_name || state.entity_id)}</option>`).join('')}</select>
      <label for="title">Title</label><input id="title" value="${escapeHTML(this._config.title || '')}" placeholder="Alarms">
      <label for="height">Maximum alarm area height in pixels (optional)</label><input id="height" type="number" min="120" value="${escapeHTML(this._config.max_height || '')}">`;
    this.shadowRoot.querySelector('#entity').value = this._config.entity || '';
    this.shadowRoot.querySelectorAll('input,select').forEach(input => input.onchange = () => {
      if (!input.checkValidity()) return;
      const key = {entity:'entity',title:'title',height:'max_height'}[input.id];
      if (!input.value) delete this._config[key];
      else this._config[key] = key === 'max_height' ? Number(input.value) : input.value;
      this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));
    });
  }
}

if (!customElements.get('dashboard-alarms-card')) customElements.define('dashboard-alarms-card',DashboardAlarmsCard);
if (!customElements.get('dashboard-alarms-card-editor')) customElements.define('dashboard-alarms-card-editor',DashboardAlarmsCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'dashboard-alarms-card'))
  window.customCards.push({type:'dashboard-alarms-card',name:'Dashboard Alarms',description:'Calendar-backed alarms with enable switches and a touch-friendly editor.'});
