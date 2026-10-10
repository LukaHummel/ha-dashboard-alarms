/* Globally loaded ringing controls, independent of dashboard/card lifecycle. */
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, character =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character]));

export class DashboardAlarmsNotifications extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._calendars = new Map();
    this._busy = new Set();
    this._errors = new Map();
    this._generation = 0;
    this._ready = () => {
      this._online = true;
      this._clearCalendars();
      this._syncHass();
    };
    this._offline = () => { this._online = false; this._render(); };
    this.shadowRoot.innerHTML = `<style>
      :host { color:var(--primary-text-color,#202124); font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif); }
      * { box-sizing:border-box; }
      dialog { width:min(720px,calc(100vw - 24px)); max-height:calc(100dvh - 24px); padding:0; border:1px solid var(--divider-color,#ddd); border-radius:24px; color:inherit; background:var(--card-background-color,#fff); box-shadow:0 20px 80px #0005; }
      dialog::backdrop { background:rgba(0,0,0,.65); }
      header { padding:28px 28px 20px; text-align:center; }
      .icon { font-size:48px; line-height:1; margin-bottom:12px; }
      h2 { margin:0; font-size:28px; } .subtitle { margin:8px 0 0; color:var(--secondary-text-color,#62656a); }
      .alarms { overflow:auto; max-height:calc(100dvh - 210px); padding:0 28px 28px; }
      article { padding:24px 0; border-top:1px solid var(--divider-color,#ddd); }
      article:first-child { padding-top:8px; border-top:0; }
      .time { font-size:clamp(44px,9vw,64px); line-height:1.15; font-weight:650; text-align:center; font-variant-numeric:tabular-nums; }
      .name { margin:10px 0 24px; text-align:center; font-size:18px; overflow-wrap:anywhere; }
      .actions { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
      button { cursor:pointer; font:inherit; font-size:26px; font-weight:600; min-width:0; min-height:112px; padding:20px 12px; border:0; border-radius:16px; color:inherit; background:var(--secondary-background-color,#eceff3); }
      button small { display:block; font-size:16px; font-weight:400; margin-top:6px; }
      .dismiss { background:var(--primary-color,#3975a9); color:var(--text-primary-color,#fff); }
      button:focus-visible { outline:3px solid var(--primary-color,#3975a9); outline-offset:4px; }
      button:disabled { opacity:.55; cursor:wait; }
      .error { color:var(--error-color,#b33b36); font-size:16px; line-height:1.5; overflow-wrap:anywhere; margin:16px 0 0; }
      .offline { padding:0 28px 20px; text-align:center; }
      @media(max-width:420px) { header { padding:24px 16px 16px; } .alarms { padding:0 16px 16px; } .actions { grid-template-columns:1fr; gap:12px; } button { min-height:96px; } }
    </style><dialog aria-labelledby="ringing-title"></dialog>`;
    this._dialog = this.shadowRoot.querySelector('dialog');
    // Escape must not silently hide a still-ringing alarm.
    this._dialog.addEventListener('cancel', event => event.preventDefault());
  }

  connectedCallback() {
    this._syncHass();
    // The frontend's root hass property is updated across all panels. Poll only
    // to discover connections/calendars; alarm updates use live WebSockets.
    this._timer = setInterval(() => this._syncHass(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._detachConnection();
    this._clearCalendars();
  }

  _clearCalendars() {
    this._generation++;
    for (const record of this._calendars.values()) record.unsubscribe?.();
    this._calendars.clear();
    this._busy.clear();
    this._errors.clear();
    this._render();
  }

  _detachConnection() {
    this._connection?.removeEventListener('ready', this._ready);
    this._connection?.removeEventListener('disconnected', this._offline);
    this._connection = null;
  }

  _syncHass() {
    const root = document.querySelector('home-assistant');
    const hass = root?.hass;
    if (!hass?.connection) {
      if (this._connection) { this._detachConnection(); this._clearCalendars(); }
      return;
    }
    this._hass = hass;
    if (this._connection !== hass.connection) {
      this._detachConnection();
      this._clearCalendars();
      this._connection = hass.connection;
      this._online = hass.connection.connected !== false;
      this._connection.addEventListener('ready', this._ready);
      this._connection.addEventListener('disconnected', this._offline);
    }
    // Inherit the active Home Assistant theme even though this lives outside
    // the dashboard's render tree.
    const theme = getComputedStyle(root);
    for (const name of ['primary-color', 'primary-text-color', 'secondary-text-color',
      'secondary-background-color', 'card-background-color', 'divider-color', 'error-color', 'text-primary-color']) {
      const value = theme.getPropertyValue(`--${name}`);
      if (value) this.style.setProperty(`--${name}`, value);
      else this.style.removeProperty(`--${name}`);
    }
    const ids = new Set(Object.values(hass.states || {})
      .filter(state => state.attributes?.dashboard_alarms && state.state !== 'unavailable')
      .map(state => state.entity_id));
    for (const [entityId, record] of this._calendars) {
      if (!ids.has(entityId)) {
        record.unsubscribe?.();
        this._calendars.delete(entityId);
      }
    }
    for (const entityId of ids) {
      let record = this._calendars.get(entityId);
      if (!record) {
        record = {};
        this._calendars.set(entityId, record);
      }
      if (this._online && !record.pending && !record.unsubscribe && Date.now() >= (record.retryAt || 0))
        this._subscribe(entityId, record);
    }
    this._render();
  }

  async _subscribe(entityId, record) {
    record.pending = true;
    const generation = this._generation;
    try {
      const unsubscribe = await this._connection.subscribeMessage(data => {
        if (generation !== this._generation || this._calendars.get(entityId) !== record) return;
        record.data = data;
        this._render();
      }, {type:'dashboard_alarms/subscribe', entity_id:entityId});
      if (generation !== this._generation || this._calendars.get(entityId) !== record || !this.isConnected)
        unsubscribe();
      else record.unsubscribe = unsubscribe;
    } catch {
      // A removed/restricted calendar should not break the other subscriptions.
      record.retryAt = Date.now() + 5000;
    } finally { record.pending = false; }
  }

  _ringing() {
    const alarms = [];
    for (const [entityId, record] of this._calendars) {
      if (record.data?.can_control === false) continue;
      for (const alarm of record.data?.alarms || []) {
        if (alarm.enabled && alarm.state === 'ringing') alarms.push({
          ...alarm, entityId, key:`${entityId}:${alarm.uid}`, timeZone:record.data.time_zone,
          snoozeMinutes:alarm.audio?.snooze_minutes ?? record.data.defaults?.snooze_minutes ?? 10,
        });
      }
    }
    return alarms.sort((left, right) => left.key.localeCompare(right.key));
  }

  _render() {
    if (!this._dialog) return;
    const alarms = this._ringing();
    const signature = JSON.stringify([alarms, this._online, [...this._busy], [...this._errors], this._hass?.locale]);
    if (signature === this._signature) return;
    this._signature = signature;
    if (!alarms.length) { this._dialog.close(); return; }
    const focus = this.shadowRoot.activeElement;
    const focusedKey = focus?.dataset.key;
    const focusedAction = focus?.dataset.action;
    this._dialog.innerHTML = `<header><div class="icon" aria-hidden="true">⏰</div>
      <h2 id="ringing-title">${alarms.length > 1 ? 'Alarms ringing' : 'Alarm ringing'}</h2>
      <p class="subtitle">Snooze for a little longer, or dismiss to stop.</p></header>
      ${!this._online ? '<p class="offline error" role="alert">Home Assistant disconnected. Reconnecting…</p>' : ''}
      <div class="alarms">${alarms.map(alarm => {
        const hour12 = this._hass?.locale?.time_format === '12' ? true :
          this._hass?.locale?.time_format === '24' ? false : undefined;
        const time = new Intl.DateTimeFormat(this._hass?.locale?.language || navigator.language,
          {timeZone:alarm.timeZone || this._hass?.config?.time_zone, hour:'numeric', minute:'2-digit', hour12})
          .format(new Date(alarm.ring_started || alarm.start));
        const disabled = !this._online || this._busy.has(alarm.key) ? 'disabled' : '';
        const error = this._errors.get(alarm.key) || alarm.audio_error;
        return `<article aria-label="${escapeHTML(alarm.name)}"><div class="time">${escapeHTML(time)}</div>
          <p class="name">${escapeHTML(alarm.name)}</p><div class="actions">
          <button data-key="${escapeHTML(alarm.key)}" data-action="snooze" ${disabled}>Snooze<small>${escapeHTML(alarm.snoozeMinutes)} minutes</small></button>
          <button class="dismiss" data-key="${escapeHTML(alarm.key)}" data-action="dismiss" ${disabled}>Dismiss<small>Stop this alarm</small></button></div>
          ${error ? `<p class="error" role="alert">${escapeHTML(error)}</p>` : ''}</article>`;
      }).join('')}</div>`;
    this._dialog.querySelectorAll('[data-action]').forEach(button => {
      button.onclick = () => this._command(button.dataset.key, button.dataset.action);
    });
    if (!this._dialog.open) this._dialog.showModal();
    else if (focusedKey) {
      [...this._dialog.querySelectorAll('[data-action]')]
        .find(button => button.dataset.key === focusedKey && button.dataset.action === focusedAction)?.focus();
    }
  }

  async _command(key, command) {
    const alarm = this._ringing().find(item => item.key === key);
    if (!alarm || !this._online || this._busy.has(key)) return;
    const generation = this._generation;
    this._busy.add(key);
    this._errors.delete(key);
    this._render();
    try {
      await this._hass.callWS({type:'dashboard_alarms/command', entity_id:alarm.entityId, uid:alarm.uid, command});
    } catch (error) {
      if (generation === this._generation) this._errors.set(key, error.message || String(error));
    } finally {
      if (generation === this._generation) { this._busy.delete(key); this._render(); }
    }
  }
}

if (!customElements.get('dashboard-alarms-notifications'))
  customElements.define('dashboard-alarms-notifications', DashboardAlarmsNotifications);

const mount = () => {
  if (window.dashboardAlarmsNotifications?.isConnected) return;
  const notifications = document.createElement('dashboard-alarms-notifications');
  window.dashboardAlarmsNotifications = notifications;
  document.body.append(notifications);
};
if (document.body) mount();
else window.addEventListener('DOMContentLoaded', mount, {once:true});
