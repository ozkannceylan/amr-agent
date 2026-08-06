/*
 * TEST HARNESS — HMI v2b, the map pane, in a real browser engine and pressed.
 *
 *     #############################################################
 *     #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
 *     #############################################################
 *
 * A NEW FILE RATHER THAN AN EDIT OF `capture_v2a_screens.mjs`. That script and
 * the captures it produced are the v2a evidence this version must be shown not
 * to have broken; a repeat that reuses its predecessor's names destroys the
 * comparison it exists to make (docs/LESSONS.md 2026-08-06). Every file below
 * is named `v2b-*` and overwrites nothing.
 *
 * Like its predecessor it speaks the Chrome DevTools Protocol over the
 * WebSocket Node 22 already has built in — no Playwright, no node_modules,
 * nothing added to any venv — and it presses the page with genuine input
 * events, so the DOM handlers are the code under test rather than the HTTP
 * endpoints behind them (EVIDENCE_HMI.md §C's residual).
 *
 * Four roles:
 *
 *     v2a_scenario_double.py   plays the PLC. It owns every verdict zones A-F show
 *     viz_double.py            plays the READ-ONLY MONITORING SERVICE. It owns
 *                              the map, the pose, the scan and every AGE
 *     hmi_server.py            the software under test, backend half
 *     the browser here         plays the OPERATOR, through the page
 *
 * THE STALE PASS IS THE POINT OF THIS SCRIPT. The localization publishes a pose
 * only on a filter update, so a standing vehicle has no pose stream at all and
 * a naive page draws a minutes-old pose as though it were live. The `stale`
 * pass freezes the pose at a known instant and photographs the page after the
 * age has crossed the display ramp — and it asserts, at the PIXEL level, that
 * the solid vehicle marker is GONE, not merely that a caption changed.
 *
 * Run (from the repository root):
 *     node hmi/tools/capture_v2b_screens.mjs
 *     node hmi/tools/capture_v2b_screens.mjs --passes stale,noobstacles
 */

import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, appendFileSync, openSync, statSync, rmSync,
  readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';

// ---------------------------------------------------------------- arguments
function arg(name, dflt) {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
}
const REPO = path.resolve(arg('repo', process.cwd()));
const OUT = path.resolve(arg('out', path.join(REPO, 'hmi/evidence/screenshots')));
const PYTHON = arg('python', 'python');
const CHROME = arg('chrome', 'C:/Program Files/Google/Chrome/Application/chrome.exe');
const DATE = arg('date', new Date().toISOString().slice(0, 10));
const CDP_PORT = parseInt(arg('cdp-port', '9334'), 10);
const OPCUA_PORT = arg('opcua-port', '4862');   // config-v2b-double.yaml's endpoint
const VIZ_PORT = arg('viz-port', '8093');
const HMI_PORT = arg('hmi-port', '8097');
const HMI_BASE = `http://127.0.0.1:${HMI_PORT}`;
const VIZ_BASE = `http://127.0.0.1:${VIZ_PORT}`;
const SCRATCH = path.join(os.tmpdir(), 'amr-hmi-v2b-screens');

const ALL_PASSES = ['live', 'stale', 'noobstacles', 'scanstopped', 'nomap',
  'monitordown', 'notconfigured', 'v2astates', 'pagestale', 'secondtab'];
const PASSES = arg('passes', ALL_PASSES.join(',')).split(',').map((s) => s.trim());

mkdirSync(OUT, { recursive: true });
mkdirSync(SCRATCH, { recursive: true });
const MANIFEST = path.join(OUT, `MANIFEST-v2b-${DATE}.txt`);
writeFileSync(MANIFEST, `HMI v2b (map pane) screenshot manifest — ${DATE}\n`
  + `produced by hmi/tools/capture_v2b_screens.mjs against\n`
  + `  hmi/tools/v2a_scenario_double.py  (the PLC)\n`
  + `  hmi/tools/viz_double.py           (the read-only monitoring service)\n\n`);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function log(...m) { console.log('[capture]', ...m); }

// ------------------------------------------------------------- child procs
const children = [];
function start(name, cmd, args) {
  const out = openSync(path.join(SCRATCH, name + '.log'), 'a');
  const child = spawn(cmd, args, { cwd: REPO, stdio: ['ignore', out, out] });
  children.push({ name, child });
  log(`started ${name} pid ${child.pid}`);
  return child;
}
function stop(name) {
  for (const e of children) {
    if (e.name !== name || e.dead) continue;
    try { process.kill(e.child.pid); } catch { /* already gone */ }
    e.dead = true;
    log(`stopped ${name}`);
  }
}
function stopAll() { for (const e of children) stop(e.name); }

async function waitFor(what, fn, timeoutMs = 40000) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch (e) { last = e.message; }
    await sleep(150);
  }
  throw new Error(`timed out waiting for ${what} (last: ${JSON.stringify(last)})`);
}
async function state() {
  const r = await fetch(HMI_BASE + '/state', { cache: 'no-store' });
  return r.json();
}
async function monitor() {
  const r = await fetch(HMI_BASE + '/monitor/state', { cache: 'no-store' });
  return r.json();
}

// ------------------------------------------------------------------- CDP --
class Cdp {
  constructor(ws) {
    this.ws = ws; this.next = 1; this.pending = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    });
  }
  static async open(url) {
    const ws = new WebSocket(url);
    await new Promise((res, rej) => {
      ws.addEventListener('open', res, { once: true });
      ws.addEventListener('error', rej, { once: true });
    });
    return new Cdp(ws);
  }
  send(method, params = {}) {
    const id = this.next++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  async evaluate(expression) {
    const r = await this.send('Runtime.evaluate',
      { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' :: ' + expression);
    return r.result.value;
  }
  async navigate(url) { await this.send('Page.navigate', { url }); await sleep(900); }
  async rect(selector) {
    const r = await this.evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return null;
      el.scrollIntoView({block:'center'});
      const b = el.getBoundingClientRect();
      return {x: b.x + b.width/2, y: b.y + b.height/2};
    })()`);
    if (!r) throw new Error(`no element ${selector}`);
    return r;
  }
  async mouse(type, x, y, extra = {}) {
    await this.send('Input.dispatchMouseEvent',
      { type, x, y, button: 'left', clickCount: 1, ...extra });
  }
  async click(selector) {
    const p = await this.rect(selector);
    await this.mouse('mouseMoved', p.x, p.y, { buttons: 0 });
    await this.mouse('mousePressed', p.x, p.y, { buttons: 1 });
    await sleep(60);
    await this.mouse('mouseReleased', p.x, p.y, { buttons: 0 });
    await sleep(140);
  }
  async press(selector) {
    const p = await this.rect(selector);
    await this.mouse('mouseMoved', p.x, p.y, { buttons: 0 });
    await this.mouse('mousePressed', p.x, p.y, { buttons: 1 });
    return p;
  }
  async release(p) { await this.mouse('mouseReleased', p.x, p.y, { buttons: 0 }); }
  async dragTo(selector, fx, fy) {
    const box = await this.evaluate(`(() => {
      const b = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
      return {x: b.x, y: b.y, w: b.width, h: b.height};
    })()`);
    await this.mouse('mouseMoved', box.x + box.w * fx, box.y + box.h * fy, { buttons: 1 });
  }
  async shot(file, caption, selector) {
    let clip;
    if (selector) {
      const b = await this.evaluate(`(() => {
        const el = document.querySelector(${JSON.stringify(selector)});
        const r = el.getBoundingClientRect();
        return {x: r.x + window.scrollX, y: r.y + window.scrollY,
                width: r.width, height: r.height};
      })()`);
      clip = { ...b, scale: 1 };
    } else {
      const metrics = await this.send('Page.getLayoutMetrics');
      const size = metrics.cssContentSize || metrics.contentSize;
      clip = { x: 0, y: 0, width: size.width, height: size.height, scale: 1 };
    }
    const r = await this.send('Page.captureScreenshot',
      { format: 'png', captureBeyondViewport: true, clip });
    const target = path.join(OUT, file);
    writeFileSync(target, Buffer.from(r.data, 'base64'));
    const bytes = statSync(target).size;
    if (bytes < 1200) throw new Error(`${file} is only ${bytes} bytes — not a render`);
    appendFileSync(MANIFEST, `${file}\n    ${caption}\n`);
    log(`shot ${file}  ${bytes} bytes  — ${caption}`);
    return bytes;
  }
}

/** What zones A–F are showing — the v2a readout, unchanged, so this version can
 *  be compared against the previous one field for field. */
async function readout(cdp, label) {
  const r = await cdp.evaluate(`(() => {
    const t = (i) => (document.getElementById(i)||{}).textContent;
    const cls = (i) => (document.getElementById(i)||{}).className;
    const stt = (i) => { const e = document.getElementById(i); if (!e) return null;
      return (e.classList.contains('unk') ? 'UNKNOWN'
            : e.classList.contains('on') ? 'ASSERTED' : 'clear')
            + ' / ' + e.querySelector('.val').textContent; };
    return {
      strip: {session: t('c_session'), link: t('c_link'), mode: t('modechip')},
      pstop: {label: t('pstop'), cls: cls('pstop'),
              disabled: document.getElementById('pstop').disabled},
      machineMode: t('machinemode'),
      selected: [0,1,2].filter(m =>
        document.getElementById('mode'+m).classList.contains('sel')),
      zoneC: {pstop: stt('s_pstop'), obstacle: stt('s_obstacle'),
              resetreq: stt('s_resetreq'), teleop: stt('s_teleop')},
      zoneD: {absent: document.getElementById('fabsent').classList.contains('on'),
              estop: stt('f_estop'), zone: stt('f_zone')},
      zoneE: {enable: t('e_enable'), ceiling: t('e_ceiling')},
      requests: {mode: t('q_mode'), pstop: t('q_pstop'), teleop: t('q_teleop'),
                 reset: t('q_reset'), traction: t('q_traction')},
    };
  })()`);
  log(label, JSON.stringify(r));
  return r;
}

/** What the MAP PANE is showing — DOM text plus a pixel census of the canvas.
 *
 *  The pixel census is here because the stale rendering is a drawing, not a
 *  caption: `vehicleFill` counts pixels at the vehicle marker's exact fill
 *  colour, so "the solid marker is gone" is an assertion about the picture and
 *  not about the sentence beside it. */
async function mapReadout(cdp, label) {
  const r = await cdp.evaluate(`(() => {
    const t = (i) => (document.getElementById(i)||{}).textContent;
    const v = (i) => { const e = document.getElementById(i);
      return e ? e.querySelector('.v').textContent : null; };
    const c = document.getElementById('mapcanvas');
    const g = c.getContext('2d');
    const d = g.getImageData(0, 0, c.width, c.height).data;
    const seen = new Set();
    let vehicleFill = 0, obstacleInk = 0, nonBlank = 0;
    for (let i = 0; i < d.length; i += 4) {
      const R = d[i], G = d[i+1], B = d[i+2], A = d[i+3];
      if (A === 0) continue;
      nonBlank++;
      seen.add(R + ',' + G + ',' + B);
      if (R === 58 && G === 160 && B === 220) vehicleFill++;       // #3aa0dc
      if (R === 185 && G === 139 && B === 216) obstacleInk++;      // #b98bd8
    }
    return {
      serial: t('mapserial'),
      pose: v('m_pose'), obstacles: v('m_obst'), map: v('m_map'), fetch: v('m_fetch'),
      staleBannerOn: document.getElementById('mapstale').classList.contains('on'),
      staleBanner: t('mapstale'),
      messageOn: document.getElementById('mapmsg').classList.contains('on'),
      message: t('mapmsg'),
      canvas: {w: c.width, h: c.height, colours: seen.size, nonBlank,
               vehicleFill, obstacleInk},
    };
  })()`);
  log(label, JSON.stringify(r));
  return r;
}

const failures = [];
function check(name, ok, detail) {
  log(ok ? `  CHECK PASS  ${name}` : `  CHECK FAIL  ${name}  ${detail || ''}`);
  if (!ok) failures.push(`${name} ${detail || ''}`);
}

// ------------------------------------------------------------- the passes --
function startViz(extra = []) {
  start('viz', PYTHON, ['hmi/tools/viz_double.py', '--port', VIZ_PORT,
    '--run-seconds', '400', ...extra]);
}
function startStack(scenario, vizArgs = [], extra = [], evidenceStem = null) {
  start('double', PYTHON, ['hmi/tools/v2a_scenario_double.py',
    '--port', OPCUA_PORT, '--scenario', scenario, '--adopt-delay', '1.2',
    '--run-seconds', '400', ...extra]);
  if (vizArgs !== null) startViz(vizArgs);
  return sleep(3500).then(() => {
    const ev = evidenceStem ? ['--evidence-csv', evidenceStem] : [];
    // `--no-monitor`, not merely "no --monitor-url": the config file names a
    // monitoring service, and "not configured" and "not answering" are two
    // different facts the pane must be able to tell apart.
    const mon = vizArgs === null ? ['--no-monitor'] : ['--monitor-url', VIZ_BASE];
    start('hmi', PYTHON, ['hmi/hmi_server.py',
      '--config', 'hmi/config-v2b-double.yaml', '--http-port', HMI_PORT,
      ...mon, ...ev]);
    return waitFor('the HMI backend to connect',
      async () => (await state()).session.state === 'CONNECTED');
  });
}
function stopStack() {
  stop('hmi'); stop('viz'); stop('double');
  for (const e of children) if (e.dead && !e.name.endsWith('-done')) e.name += '-done';
  return sleep(1500);
}

function readEvidenceCsv(stem) {
  const dir = path.dirname(path.resolve(REPO, stem));
  const base = path.basename(stem, '.csv');
  const files = readdirSync(dir).filter((f) => f.startsWith(base) && f.endsWith('.csv'))
    .map((f) => path.join(dir, f))
    .sort((a, b) => statSync(a).mtimeMs - statSync(b).mtimeMs);
  if (!files.length) throw new Error(`no evidence CSV for ${stem}`);
  const lines = readFileSync(files[files.length - 1], 'utf8').trim().split(/\r?\n/);
  const head = lines[0].split(',');
  return { path: files[files.length - 1],
    rows: lines.slice(1).map((l) => {
      const cells = l.split(',');
      return Object.fromEntries(head.map((h, i) => [h, cells[i]]));
    }) };
}

async function openTab() {
  const r = await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?url=about:blank`,
    { method: 'PUT' });
  const t = await r.json();
  const c = await Cdp.open(t.webSocketDebuggerUrl);
  c.targetId = t.id;
  await c.send('Page.enable');
  await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride',
    { width: 1680, height: 1750, deviceScaleFactor: 1, mobile: false });
  return c;
}
async function closeTab(c) {
  try { await fetch(`http://127.0.0.1:${CDP_PORT}/json/close/${c.targetId}`); }
  catch { /* the browser is going away anyway */ }
  try { c.ws.close(); } catch { /* already closed */ }
}

/** Clear the §14.9 boot latches so a pass photographs a coherent frame. */
async function clearLatches(cdp) {
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await cdp.click('#pstop');
  await sleep(500);
  const p = await cdp.press('#reset');
  await sleep(1000);
  await cdp.release(p);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
}

// ---- 1. the map, live -----------------------------------------------------
async function passLive(cdp) {
  await startStack('coldstart', ['--scenario', 'live'], ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await cdp.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(1500);

  const m = await mapReadout(cdp, '00 map live');
  check('the WHOLE map is painted, not a crop or a blank',
    m.canvas.colours >= 3 && m.canvas.nonBlank > 10000
    && /606 x 410 cells/.test(m.map) && /whole map/.test(m.map),
    `${m.canvas.colours} colours, ${m.canvas.nonBlank} px, map row "${m.map}"`);
  check('free, occupied and UNKNOWN are all drawn — unknown is not drawn as free',
    m.canvas.colours >= 3, String(m.canvas.colours));
  check('the vehicle marker is drawn SOLID while the pose is fresh',
    m.canvas.vehicleFill > 8, `${m.canvas.vehicleFill} px at the marker fill colour`);
  check('the pose is labelled with its AGE and is never called live',
    /as of /.test(m.pose) && !/LAST KNOWN/.test(m.pose) && !/live/i.test(m.pose),
    m.pose);
  check('obstacles are present, in the three classes the sensor reports',
    m.canvas.obstacleInk > 20 && /distance returns/.test(m.obstacles)
    && /beyond range/.test(m.obstacles) && /invalid/.test(m.obstacles), m.obstacles);
  check('the obstacle row makes no verdict: no "clear", "safe", "danger" or "near"',
    !/(clear|safe|danger|near)/i.test(m.obstacles.replace(/beyond range/g, '')),
    m.obstacles);
  check('the serial roots the pane even at n = 1', m.serial === 'F001', m.serial);
  await cdp.shot(`v2b-00-map-live-vehicle-and-obstacles-${DATE}.png`,
    'THE MAP PANE, LIVE: the whole 606 x 410 warehouse map at 0.05 m (30.3 x 20.5 m, '
    + 'never a crop), the vehicle drawn solid with "pose as of N s" attached to the '
    + 'marker, and the lidar returns drawn where the monitoring service placed them. '
    + 'Every row carries the age of the datum it came from', '#mapzone');
  await cdp.shot(`v2b-01-whole-page-map-beside-controls-${DATE}.png`,
    'the whole operator page with the map pane as a third column: zones A-F are '
    + 'unchanged — same controls, same ids, same renderings — and no caption anywhere '
    + 'merges a monitoring-plane value with a PLC value');

  // The view controls are DRAWING and nothing else. The check is that the eight
  // requests on the wire are bit-for-bit what they were before the zoom: a view
  // transform that moved a request would be a control, and this is the assertion
  // that it is not one.
  const before = JSON.stringify((await state()).requests);
  await cdp.click('#mapin');
  await cdp.click('#mapin');
  await sleep(500);
  const zoomed = await mapReadout(cdp, '01 zoomed in');
  const after = JSON.stringify((await state()).requests);
  check('zooming is drawing: not one of the eight written values moved',
    before === after, `${before} -> ${after}`);
  check('and the zoomed view is still a picture of the same map',
    zoomed.canvas.colours >= 3 && zoomed.canvas.vehicleFill > 8
    && zoomed.map === m.map, zoomed.map);
  await cdp.shot(`v2b-02-map-zoomed-${DATE}.png`,
    'the same map zoomed in: a view transform is drawing. It derives no value, '
    + 'changes no datum and posts nothing', '#mapzone');
  await cdp.click('#mapfit');
  await sleep(300);
  await stopStack();
}

// ---- 2. THE STALE POSE ----------------------------------------------------
async function passStale(cdp) {
  // The pose stops advancing 4 s in — which is exactly what AMCL does the
  // moment the vehicle stops, because it publishes only on a filter update.
  // 25 s, not 4: the cold-start sequence above takes several seconds, and a
  // freeze that lands during it would leave this pass with no FRESH sample to
  // compare the stale one against - the comparison IS the check.
  await startStack('coldstart', ['--scenario', 'live', '--freeze-pose-after', '25'],
    ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await waitFor('a fresh pose to photograph first',
    async () => (await monitor()).state.pose_age_ms < 900);
  await sleep(400);

  const fresh = await mapReadout(cdp, '02a before the pose froze');
  check('the pose is fresh before the freeze - the comparison has a baseline',
    fresh.canvas.vehicleFill > 8 && !/LAST KNOWN/.test(fresh.pose),
    `${fresh.canvas.vehicleFill} px, "${fresh.pose}"`);
  const ramp = (await monitor()).monitor;
  log(`display ramp published by the backend: ${ramp.age_ramp_start_ms} .. `
    + `${ramp.age_ramp_full_ms} ms`);

  await waitFor('the pose age to cross the display ramp',
    async () => (await monitor()).state.pose_age_ms > ramp.age_ramp_full_ms + 3000,
    90000);
  await sleep(600);
  const m = await mapReadout(cdp, '02b pose STALE');
  const age = (await monitor()).state.pose_age_ms;

  check('the marker no longer has ANY solid fill — the picture changed, not only '
    + 'the caption',
    fresh.canvas.vehicleFill > 20 && m.canvas.vehicleFill === 0,
    `${fresh.canvas.vehicleFill} px fresh -> ${m.canvas.vehicleFill} px stale`);
  check('the readout says LAST KNOWN and gives the age',
    /LAST KNOWN/.test(m.pose) && /as of /.test(m.pose), m.pose);
  check('the banner says where the vehicle WAS, not where it is',
    m.staleBannerOn && /where the vehicle WAS/.test(m.staleBanner)
    && /not where it is/.test(m.staleBanner), m.staleBanner.slice(0, 90));
  check('the banner states the reason a standing vehicle looks like this',
    /publishes\s+only when its filter updates/.test(
      m.staleBanner.replace(/\s+/g, ' ')), m.staleBanner.slice(0, 160));
  check('the page does not guess between a standing vehicle and a stopped one',
    /does not guess/.test(m.staleBanner));
  check('the OBSTACLE layer is still fresh at the same moment — the two ages are '
    + 'independent and neither is inferred from the other',
    /distance returns/.test(m.obstacles) && m.canvas.obstacleInk > 20, m.obstacles);
  check('the map itself is untouched by a stale pose',
    /606 x 410 cells/.test(m.map), m.map);
  log(`pose age at capture: ${age} ms`);
  await cdp.shot(`v2b-03-pose-STALE-last-known-position-${DATE}.png`,
    `THE STALE POSE, ${(age / 1000).toFixed(1)} s old: the marker is hollow and dashed `
    + 'with no fill at all, labelled LAST KNOWN POSITION with its age, and the banner '
    + 'says the vehicle was there, not that it is. The localization publishes only on a '
    + 'filter update, so this is also what a STANDING vehicle looks like — and the page '
    + 'says it cannot tell those apart rather than guessing', '#mapzone');
  await cdp.shot(`v2b-04-whole-page-pose-stale-${DATE}.png`,
    'the same stale pose on the whole page: zones A-F are unaffected, because the two '
    + 'planes are two sources and the age of one says nothing about the other');
  await stopStack();
}

// ---- 3. obstacles absent --------------------------------------------------
async function passNoObstacles(cdp) {
  await startStack('coldstart', ['--scenario', 'noobstacles'], ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await sleep(1200);
  const m = await mapReadout(cdp, '03 no distance returns');
  check('the row says NO DISTANCE RETURNS, with the beyond-range count beside it',
    /no distance returns in this scan/.test(m.obstacles)
    && /beyond range/.test(m.obstacles), m.obstacles);
  check('it never says clear, safe or "no obstacles" — an empty horizon is a '
    + 'measurement, not an absence of danger',
    !/no obstacles/i.test(m.obstacles) && !/\bsafe\b/i.test(m.obstacles)
    && !/\bclear\b/i.test(m.obstacles.replace(/clear_beyond_range/g, '')),
    m.obstacles);
  check('nothing is drawn for the returns', m.canvas.obstacleInk === 0,
    String(m.canvas.obstacleInk));
  check('the pose and the map are unaffected',
    /as of /.test(m.pose) && /606 x 410/.test(m.map), m.pose);
  await cdp.shot(`v2b-05-obstacles-absent-empty-horizon-${DATE}.png`,
    'OBSTACLES ABSENT: every beam returned beyond its range, which is the sensor '
    + 'MEASURING an open horizon rather than failing. The pane reports the three classes '
    + 'the sensor reported and calls the result neither clear nor safe', '#mapzone');
  await stopStack();
}

// ---- 4. the scan stops arriving ------------------------------------------
async function passScanStopped(cdp) {
  await startStack('coldstart', ['--scenario', 'live', '--stop-scan-after', '4'],
    ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await waitFor('the obstacle age to cross the ramp',
    async () => (await monitor()).state.obstacles_age_ms > 9000, 60000);
  await sleep(500);
  const m = await mapReadout(cdp, '04 scan stopped');
  const age = (await monitor()).state.obstacles_age_ms;
  check('a stale obstacle layer is NOT rendered as an empty one',
    /distance returns/.test(m.obstacles) && !/no distance returns/.test(m.obstacles),
    m.obstacles);
  check('and it carries its own age', /as of /.test(m.obstacles), m.obstacles);
  await cdp.shot(`v2b-06-obstacles-stale-not-emptied-${DATE}.png`,
    `THE SCAN STOPPED ARRIVING ${(age / 1000).toFixed(1)} s ago: the returns are drawn `
    + 'hollow and labelled with their age. The pane has no rendering that means "there '
    + 'is nothing there now", so a dead sensor can never read as an empty aisle',
    '#mapzone');
  await stopStack();
}

// ---- 5. no map yet --------------------------------------------------------
async function passNoMap(cdp) {
  await startStack('coldstart', ['--scenario', 'nomap'], ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await sleep(1200);
  const m = await mapReadout(cdp, '05 no map');
  check('the pane says no map has arrived and draws nothing',
    m.messageOn && /No map has arrived/.test(m.message), m.message);
  check('a position without its map is not drawn as a picture',
    m.canvas.vehicleFill === 0 && m.canvas.obstacleInk === 0,
    `${m.canvas.vehicleFill}/${m.canvas.obstacleInk}`);
  await cdp.shot(`v2b-07-no-map-received-${DATE}.png`,
    'NO MAP HAS ARRIVED from this vehicle yet: nothing is drawn, because a position '
    + 'without the map it is expressed in is not a picture', '#mapzone');
  await stopStack();
}

// ---- 6. the monitoring service dies mid-run -------------------------------
async function passMonitorDown(cdp) {
  await startStack('coldstart', ['--scenario', 'live'], ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await cdp.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(1200);
  const before = await readout(cdp, '06a zones A-F before the outage');
  const hbBefore = (await state()).heartbeat.value;

  stop('viz');
  await sleep(3500);

  const m = await mapReadout(cdp, '06b monitoring service down');
  const after = await readout(cdp, '06c zones A-F after the outage');
  const s = await state();
  check('the pane greys and says the service is not answering',
    m.messageOn && /not answering/.test(m.message), m.message.slice(0, 120));
  check('it shows NO last values at all — an unreachable source is not a source '
    + 'of last values',
    m.pose === '—' && m.obstacles === '—' && m.map === '—',
    `${m.pose} / ${m.obstacles} / ${m.map}`);
  check('nothing is left drawn on the canvas',
    m.canvas.vehicleFill === 0 && m.canvas.obstacleInk === 0,
    `${m.canvas.vehicleFill}/${m.canvas.obstacleInk}`);
  check('THE PROCESS PLANE IS UNTOUCHED: the session is still up and the mode still '
    + 'in force',
    after.strip.session === 'CONNECTED' && after.machineMode === before.machineMode
    && after.zoneC.resetreq === before.zoneC.resetreq,
    `${after.strip.session} / ${after.machineMode}`);
  check('the heartbeat kept advancing across the outage',
    s.heartbeat.value !== hbBefore && s.heartbeat.running === true,
    `${hbBefore} -> ${s.heartbeat.value}`);
  await cdp.shot(`v2b-08-monitoring-service-down-${DATE}.png`,
    'THE MONITORING SERVICE STOPPED: the map pane greys and shows nothing — no map, no '
    + 'position, no obstacles, and no last values. The process zones beside it are '
    + 'unchanged and the heartbeat never paused: two planes, two sources, and the '
    + 'failure of one is not the failure of the other');
  await stopStack();
}

// ---- 7. no monitoring service configured at all ---------------------------
async function passNotConfigured(cdp) {
  await startStack('coldstart', null, ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await sleep(2000);
  const m = await mapReadout(cdp, '07 not configured');
  check('the pane says no monitoring service is configured',
    m.messageOn && /No monitoring service is configured/.test(m.message), m.message);
  await cdp.shot(`v2b-09-monitoring-not-configured-${DATE}.png`,
    'a backend started with no monitoring service configured at all: the pane says so '
    + 'in words and the rest of the page is exactly the v2a page', '#mapzone');
  await stopStack();
}

// ---- 8. the v2a states, with the pane present -----------------------------
async function passV2aStates(cdp) {
  await startStack('coldstart', ['--scenario', 'live'], ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await sleep(1500);

  let r = await readout(cdp, '08a cold start, link up');
  check('v2a unbroken: the stop boots ENGAGED and looks armed',
    r.pstop.cls.includes('engaged') && !r.pstop.cls.includes('unavailable'),
    r.pstop.label);
  check('v2a unbroken: §14.9 signature — mode NONE, ceiling 0.00',
    r.machineMode === 'NONE' && r.zoneE.ceiling.includes('0.00'),
    JSON.stringify(r.zoneE));
  check('v2a unbroken: connecting cleared nothing',
    r.zoneC.pstop.includes('LATCHED') && r.zoneC.resetreq.includes('REQUIRED'),
    JSON.stringify(r.zoneC));
  await cdp.shot(`v2b-10-v2a-cold-start-unbroken-${DATE}.png`,
    'the v2a cold start, re-photographed with the map pane present: PROCESS STOP '
    + 'ENGAGED and armed, process stop latched, reset required, envelope withheld. '
    + 'Adding a map changed none of it');

  await cdp.click('#pstop');
  await sleep(900);
  r = await readout(cdp, '08b stop released');
  check('v2a unbroken: PS1 — the request cleared and the LATCH did not',
    r.requests.pstop === 'false' && r.zoneC.pstop.includes('LATCHED'),
    `${r.requests.pstop} / ${r.zoneC.pstop}`);
  await cdp.shot(`v2b-11-v2a-stop-released-latch-stands-${DATE}.png`,
    'the operator releases the process stop with the map pane present: the request goes '
    + 'FALSE and the latch visibly does not clear. Request and latch are still two things');

  const p = await cdp.press('#reset');
  await sleep(1300);
  r = await readout(cdp, '08c reset held');
  check('v2a unbroken: RESET is a level and is held', r.requests.reset === 'true',
    r.requests.reset);
  await cdp.release(p);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
  await cdp.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(700);
  await cdp.click('#enable');
  await sleep(300);
  await cdp.press('#pad');
  await cdp.dragTo('#pad', 0.5, 0.18);
  await sleep(900);
  r = await readout(cdp, '08d teleop driving');
  check('v2a unbroken: the joystick still streams a request while the map polls',
    Number(r.requests.traction) > 0.4 && r.requests.teleop === 'true',
    `${r.requests.traction} / ${r.requests.teleop}`);
  const m = await mapReadout(cdp, '08e map while driving');
  check('and the map pane is live at the same moment',
    /as of /.test(m.pose) && m.canvas.vehicleFill > 20, m.pose);
  await cdp.shot(`v2b-12-v2a-teleop-driving-with-map-${DATE}.png`,
    'TELEOP in force, the enable asserted and the joystick held forward, with the live '
    + 'map beside it. The teleop request stream and the map poll are two independent '
    + 'channels and neither delayed the other');
  await cdp.release(await cdp.rect('#pad'));
  await stopStack();
}

// ---- 9. H6 with the map pane running --------------------------------------
async function passPageStale(cdp) {
  await startStack('coldstart', ['--scenario', 'live'], ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await cdp.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await cdp.click('#enable');
  await sleep(900);

  // BLOCK ONLY /state. The map pane keeps polling at full rate, which is
  // exactly the situation V2B-DESIGN §2.2 exists for: if a map fetch counted as
  // the beacon, this page would keep the enable armed with its control channel
  // dead.
  await cdp.send('Network.enable');
  // The pattern is the EXACT url, not '*/state': that wildcard also matches
  // /monitor/state, which would have stopped the map pane too and made this
  // pass prove nothing.
  await cdp.send('Network.setBlockedURLs', { urls: [`${HMI_BASE}/state`] });
  await sleep(3000);
  const s = await state();
  const m = await mapReadout(cdp, '09 /state blocked, map still polling');
  check('H6 fired even though the map pane was polling throughout',
    s.page.state === 'STALE' || s.page.drops >= 1,
    `page=${s.page.state} drops=${s.page.drops}`);
  check('the five deadman requests went to rest, the enable included',
    s.requests.HmiTeleopRequest === false && s.requests.HmiTractionRequest === 0,
    JSON.stringify(s.requests));
  check('the two STANDING controls were untouched by the page loss',
    s.requests.HmiProcessStopRequest === false && s.requests.HmiDriveModeRequest === 1,
    `${s.requests.HmiProcessStopRequest} / ${s.requests.HmiDriveModeRequest}`);
  check('the heartbeat kept running', s.heartbeat.running === true);
  check('and the map pane was demonstrably still fetching all the while',
    /ms round trip/.test(m.fetch), m.fetch);
  await cdp.shot(`v2b-13-page-beacon-stale-while-map-polls-${DATE}.png`,
    'THE CONTROL CHANNEL DIED WHILE THE MAP PANE KEPT POLLING: only GET /state was '
    + 'blocked. The H6 deadman still fired and the enable was dropped, because the '
    + 'backend does not count a monitoring-plane fetch as a sign of life on the '
    + 'channel that carries the operator\'s requests');
  await cdp.send('Network.setBlockedURLs', { urls: [] });
  await sleep(1500);
  await stopStack();
}

// ---- 10. the second tab, re-run because the beacon path changed -----------
async function passSecondTab(cdpA) {
  const STEM = `hmi/evidence/hmi-cycles-${DATE}-v2b-secondtab.csv`;
  await startStack('coldstart', ['--scenario', 'live'], ['--with-safety-mirrors'], STEM);
  await cdpA.navigate(HMI_BASE + '/');
  await clearLatches(cdpA);
  await cdpA.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(600);
  let s = await state();
  check('second tab, setup: the backend holds stop RELEASED and mode TELEOP',
    s.controls.process_stop === false && s.controls.drive_mode === 1,
    JSON.stringify(s.controls));

  const cdpB = await openTab();
  await cdpB.navigate(HMI_BASE + '/');
  await sleep(1800);
  let rb = await readout(cdpB, 'B1 second tab opened mid-scenario');
  check('a second page renders the BACKEND\'s standing values, not the boot values',
    !rb.pstop.cls.includes('engaged') && rb.pstop.label === 'PROCESS STOP'
    && rb.selected.length === 1 && rb.selected[0] === 1,
    rb.pstop.label + ' selected=' + JSON.stringify(rb.selected));

  await cdpA.click('#pstop');
  await waitFor('the PLC to latch the stop',
    async () => (await state()).metrics.ForkliftProcessStopActive === true);
  await sleep(800);
  rb = await readout(cdpB, 'B2 the other tab follows the backend');
  check('the other tab followed the backend and renders ENGAGED too',
    rb.pstop.cls.includes('engaged'), rb.pstop.label);
  const cycleBefore = Number((await state()).write.cycles);

  await cdpA.send('Page.bringToFront');
  await sleep(300);
  const walked = await cdpB.evaluate(`(() => {
    try {
      Object.defineProperty(document, 'visibilityState',
        { configurable: true, get: () => 'hidden' });
    } catch (e) { /* already hidden */ }
    document.dispatchEvent(new Event('visibilitychange'));
    window.dispatchEvent(new Event('blur'));
    return document.visibilityState;
  })()`);
  log('B3 backgrounded — visibilityState ' + walked);
  await sleep(3200);

  s = await state();
  check('backgrounding the non-acting page changed NEITHER standing value — the '
    + 'engaged stop is still engaged',
    s.requests.HmiProcessStopRequest === true && s.requests.HmiDriveModeRequest === 1,
    `stop=${s.requests.HmiProcessStopRequest} mode=${s.requests.HmiDriveModeRequest}`);
  const rA = await readout(cdpA, 'A after the other tab was backgrounded');
  check('the operator\'s own screen and the wire still agree — ENGAGED',
    rA.pstop.cls.includes('engaged') && rA.requests.pstop === 'true',
    rA.pstop.label + ' / ' + rA.requests.pstop);
  const csv = readEvidenceCsv(STEM);
  const after = csv.rows.filter((r) => Number(r.cycle) > cycleBefore);
  const badStop = after.filter((r) => r.HmiProcessStopRequest !== 'True');
  const badMode = after.filter((r) => r.HmiDriveModeRequest !== '1');
  check(`every one of the ${after.length} write cycles after the background still `
    + 'wrote the stop engaged and the mode TELEOP',
    after.length > 10 && badStop.length === 0 && badMode.length === 0,
    `cycles=${after.length} stop-flips=${badStop.length} mode-flips=${badMode.length} `
    + `csv=${path.basename(csv.path)}`);
  await cdpA.shot(`v2b-14-second-tab-stop-stays-engaged-${DATE}.png`,
    'THE SECOND-TAB PATH WALKED AGAIN, because v2b changed the beacon\'s input set: a '
    + 'second tab was opened, the operator engaged the stop here, and the second tab was '
    + 'backgrounded with its visibilitychange and blur handlers fired. The engaged stop '
    + 'is still engaged, on the wire and on this screen');
  await closeTab(cdpB);
  await stopStack();
}

// --------------------------------------------------------------------- main
let chrome, cdp;
try {
  // A FRESH profile directory per run, rather than a reused one wiped at start:
  // a straggler browser from an earlier run holds a lock on the old directory,
  // and the instrument must not fail for a reason that has nothing to do with
  // the page under test.
  const profile = path.join(SCRATCH, 'profile-' + Date.now());
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* fresh */ }
  chrome = start('chrome', CHROME, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`,
    '--window-size=1700,1780', 'about:blank',
  ]);
  const target = await waitFor('chrome to expose a page target', async () => {
    const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
    const page = list.find((t) => t.type === 'page');
    return page ? page.webSocketDebuggerUrl : null;
  }, 30000);
  cdp = await Cdp.open(target);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride',
    { width: 1680, height: 1750, deviceScaleFactor: 1, mobile: false });
  const ver = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`)).json();
  log('browser', ver.Browser);
  appendFileSync(MANIFEST, `browser: ${ver.Browser}\n\n`);

  const RUNNERS = {
    live: passLive, stale: passStale, noobstacles: passNoObstacles,
    scanstopped: passScanStopped, nomap: passNoMap, monitordown: passMonitorDown,
    notconfigured: passNotConfigured, v2astates: passV2aStates,
    pagestale: passPageStale, secondtab: passSecondTab,
  };
  for (const name of ALL_PASSES) {
    if (!PASSES.includes(name)) { log(`pass ${name} SKIPPED (--passes)`); continue; }
    log(`--- pass ${name} ---`);
    await RUNNERS[name](cdp);
  }

  log('--- checks ---');
  if (failures.length) {
    log(`FAILED ${failures.length} check(s):`);
    for (const f of failures) log('  ' + f);
    appendFileSync(MANIFEST, `\nFAILED CHECKS: ${failures.length}\n`
      + failures.map((f) => '  ' + f).join('\n') + '\n');
    process.exitCode = 1;
  } else {
    log('every check passed');
    appendFileSync(MANIFEST, `\nall checks passed\n`);
  }
} catch (err) {
  console.error('[capture] FAILED', err);
  process.exitCode = 1;
} finally {
  stopAll();
  await sleep(800);
  // Chrome's DevTools WebSocket keeps Node's event loop alive on its own, so an
  // unclosed one leaves the instrument running long after its last check.
  try { cdp && cdp.ws.close(); } catch { /* already closed */ }
  await sleep(200);
  process.exit(process.exitCode || 0);
}
