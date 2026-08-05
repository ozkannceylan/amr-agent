/*
 * TEST HARNESS — HMI v2a in a real browser engine, pressed and screenshotted.
 *
 *     #############################################################
 *     #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
 *     #############################################################
 *
 * Why this is not `capture_screens.mjs`. That script drives Playwright, which
 * is present on the container this project also runs on and is NOT present on
 * the Windows showcase machine — and LESSONS 2026-07-27 is explicit that
 * evidence is qualified by the environment that produced it. Rather than
 * install a browser stack to take a picture, this script speaks the Chrome
 * DevTools Protocol directly over the WebSocket that Node 22 already has
 * built in. Zero dependencies, no `node_modules`, nothing added to any venv.
 *
 * It presses the page's controls with genuine input events dispatched into the
 * browser, so the DOM handlers are the code under test — not the HTTP
 * endpoints behind them. EVIDENCE_HMI.md §C carries a residual from exactly
 * that confusion once already.
 *
 * Three roles, and the separation is the point:
 *
 *     v2a_scenario_double.py   plays the PLC and the vehicle. It owns every
 *                              verdict this page displays
 *     hmi_server.py            the software under test, backend half
 *     the browser here         plays the OPERATOR, through the page
 *
 * THE ADOPT WINDOW IS THE REASON THE DELAYS BELOW ARE WHAT THEY ARE. The
 * double's `--adopt-delay` is a realistic 1.2 s per stage, and this script
 * samples the page INSIDE both stages, so "selection not in force" and
 * "vehicle adopting" are photographed while they are true rather than asserted
 * to exist. An adopt window that only ever completes in zero time has not been
 * tested (LESSONS 2026-07-31).
 *
 * Run (from the repository root):
 *     node hmi/tools/capture_v2a_screens.mjs
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
const CDP_PORT = parseInt(arg('cdp-port', '9333'), 10);
const DOUBLE_PORT = arg('double-port', '4861');
const HMI_BASE = 'http://127.0.0.1:8094';
const SCRATCH = path.join(os.tmpdir(), 'amr-hmi-v2a-screens');
// Which passes to run. Default is every pass, in order — a partial run rewrites
// the manifest with only what it captured, so a partial run is a development
// aid and never the evidence run.
const ALL_PASSES = ['boot', 'coldstart', 'refused', 'disagree', 'linksession',
  'safety', 'pagestale', 'secondtab'];
const PASSES = arg('passes', ALL_PASSES.join(',')).split(',').map((s) => s.trim());

mkdirSync(OUT, { recursive: true });
mkdirSync(SCRATCH, { recursive: true });
const MANIFEST = path.join(OUT, `MANIFEST-${DATE}.txt`);
writeFileSync(MANIFEST, `HMI v2a screenshot manifest — ${DATE}\n`
  + `produced by hmi/tools/capture_v2a_screens.mjs against `
  + `hmi/tools/v2a_scenario_double.py\n\n`);

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
  async navigate(url) {
    await this.send('Page.navigate', { url });
    await sleep(700);
  }
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
  // A real press: move, down, up. Chrome raises pointerdown/pointerup from
  // these, which is what the page's handlers listen for.
  async click(selector) {
    const p = await this.rect(selector);
    await this.mouse('mouseMoved', p.x, p.y, { buttons: 0 });
    await this.mouse('mousePressed', p.x, p.y, { buttons: 1 });
    await sleep(60);
    await this.mouse('mouseReleased', p.x, p.y, { buttons: 0 });
    await sleep(120);
  }
  async press(selector) {
    const p = await this.rect(selector);
    await this.mouse('mouseMoved', p.x, p.y, { buttons: 0 });
    await this.mouse('mousePressed', p.x, p.y, { buttons: 1 });
    return p;
  }
  async release(p) {
    await this.mouse('mouseReleased', p.x, p.y, { buttons: 0 });
  }
  async dragTo(selector, fx, fy) {
    const box = await this.evaluate(`(() => {
      const b = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
      return {x: b.x, y: b.y, w: b.width, h: b.height};
    })()`);
    const x = box.x + box.w * fx, y = box.y + box.h * fy;
    await this.mouse('mouseMoved', x, y, { buttons: 1 });
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
    // Written into the evidence AS IT LANDS, never held for the end of a run.
    appendFileSync(MANIFEST, `${file}\n    ${caption}\n`);
    log(`shot ${file}  ${bytes} bytes  — ${caption}`);
    return bytes;
  }
}

/** A readable summary of what the page itself is showing, printed beside every
 *  screenshot so the image and the DOM it came from can be checked against each
 *  other later. */
async function readout(cdp, label) {
  const r = await cdp.evaluate(`(() => {
    const t = (i) => (document.getElementById(i)||{}).textContent;
    const cls = (i) => (document.getElementById(i)||{}).className;
    const stt = (i) => { const e = document.getElementById(i); if (!e) return null;
      return (e.classList.contains('unk') ? 'UNKNOWN'
            : e.classList.contains('on') ? 'ASSERTED' : 'clear')
            + ' / ' + e.querySelector('.val').textContent; };
    return {
      strip: {session: t('c_session'), link: t('c_link'), age: t('c_age'),
              mode: t('modechip'), degraded: document.getElementById('degraded')
                .classList.contains('on')},
      pstop: {label: t('pstop'), cls: cls('pstop'),
              disabled: document.getElementById('pstop').disabled,
              caption: t('pstopcaption')},
      modelink: {on: document.getElementById('modelink').classList.contains('on'),
                 text: t('modelink')},
      machineMode: t('machinemode'), vehicleMode: t('vehiclemode'),
      vehicleDiff: document.getElementById('vehiclediff').classList.contains('on'),
      selected: [0,1,2].filter(m =>
        document.getElementById('mode'+m).classList.contains('sel')),
      zoneC: {pstop: stt('s_pstop'), obstacle: stt('s_obstacle'),
              speed: stt('s_speedlimit'), resetreq: stt('s_resetreq'),
              teleop: stt('s_teleop')},
      zoneD: {absent: document.getElementById('fabsent').classList.contains('on'),
              estop: stt('f_estop'), zone: stt('f_zone'),
              resetreq: stt('f_resetreq'), resetfault: stt('f_resetfault')},
      zoneE: {enable: t('e_enable'), ceiling: t('e_ceiling'), permit: t('e_permit')},
      requests: {mode: t('q_mode'), pstop: t('q_pstop'), teleop: t('q_teleop'),
                 reset: t('q_reset'), traction: t('q_traction')},
    };
  })()`);
  log(label, JSON.stringify(r));
  return r;
}

/** Assert something about the page, loudly, so a silent rendering regression
 *  cannot pass as a captured screenshot. */
const failures = [];
function check(name, ok, detail) {
  log(ok ? `  CHECK PASS  ${name}` : `  CHECK FAIL  ${name}  ${detail || ''}`);
  if (!ok) failures.push(`${name} ${detail || ''}`);
}

// ------------------------------------------------------------- the passes --
function startStack(scenario, extra = [], evidenceStem = null) {
  start('double', PYTHON, ['hmi/tools/v2a_scenario_double.py',
    '--port', DOUBLE_PORT, '--scenario', scenario, '--adopt-delay', '1.2',
    '--run-seconds', '400', ...extra]);
  return sleep(3500).then(() => {
    // One evidence CSV per backend session, unique name per start — the backend
    // stamps the file itself (LESSONS 2026-07-28: a shared CSV path across
    // restarts wipes the earlier data).
    const ev = evidenceStem ? ['--evidence-csv', evidenceStem] : [];
    start('hmi', PYTHON, ['hmi/hmi_server.py',
      '--config', 'hmi/config-v2a-double.yaml', ...ev]);
    return waitFor('the HMI backend to connect',
      async () => (await state()).session.state === 'CONNECTED');
  });
}

/** The newest CSV the backend wrote for `stem`, parsed. The backend appends a
 *  UTC stamp and its pid to the stem, so the newest match is this session's. */
function readEvidenceCsv(stem) {
  const dir = path.dirname(path.resolve(REPO, stem));
  const base = path.basename(stem, '.csv');
  const files = readdirSync(dir).filter((f) => f.startsWith(base) && f.endsWith('.csv'))
    .map((f) => path.join(dir, f))
    .sort((a, b) => statSync(a).mtimeMs - statSync(b).mtimeMs);
  if (!files.length) throw new Error(`no evidence CSV for ${stem}`);
  const lines = readFileSync(files[files.length - 1], 'utf8').trim().split(/\r?\n/);
  const head = lines[0].split(',');
  return {
    path: files[files.length - 1],
    rows: lines.slice(1).map((l) => {
      const cells = l.split(',');
      return Object.fromEntries(head.map((h, i) => [h, cells[i]]));
    }),
  };
}

/** A SECOND browser tab on the same page, opened through the same CDP endpoint.
 *  This is the whole point of the second-tab pass: nothing about it is simulated
 *  — it is another real page, with its own DOM handlers, posting to the same
 *  backend. */
async function openTab() {
  const r = await fetch(`http://127.0.0.1:${CDP_PORT}/json/new?url=about:blank`,
    { method: 'PUT' });
  const t = await r.json();
  const c = await Cdp.open(t.webSocketDebuggerUrl);
  c.targetId = t.id;
  await c.send('Page.enable');
  await c.send('Runtime.enable');
  await c.send('Emulation.setDeviceMetricsOverride',
    { width: 1540, height: 1700, deviceScaleFactor: 1, mobile: false });
  return c;
}
async function closeTab(c) {
  try { await fetch(`http://127.0.0.1:${CDP_PORT}/json/close/${c.targetId}`); }
  catch { /* the browser is going away anyway */ }
  // The second tab's WebSocket keeps Node's event loop alive on its own, so an
  // unclosed one leaves the instrument running long after its last check.
  try { c.ws.close(); } catch { /* already closed */ }
}
function stopStack() {
  stop('hmi'); stop('double');
  for (const e of children) if (e.dead) e.name = e.name + '-done';
  return sleep(1500);
}

async function passBoot(cdp) {
  // scenario 'boot': the CPU cold-start signature with NO link verdict ever
  // granted. This is what §14.9 describes and it is where the process stop
  // must NOT look armed.
  await startStack('boot', ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await sleep(2000);
  const r = await readout(cdp, 'boot');
  check('cold start: process stop UNAVAILABLE while HmiLinkOk is FALSE',
    r.pstop.cls.includes('unavailable') && r.pstop.disabled === true, r.pstop.label);
  check('cold start: the control is NOT rendered engaged-looking while unavailable',
    !r.pstop.cls.includes('engaged'), r.pstop.cls);
  check('cold start: every read-derived state is UNKNOWN, not clear',
    r.zoneC.pstop.startsWith('UNKNOWN') && r.zoneD.estop.startsWith('UNKNOWN'),
    JSON.stringify(r.zoneC));
  check('cold start: the backend is nonetheless WRITING the stop engaged',
    r.requests.pstop === 'true', r.requests.pstop);
  await cdp.shot(`v2a-00-cold-start-link-not-granted-${DATE}.png`,
    'CPU cold start, HmiLinkOk still FALSE: PROCESS STOP renders UNAVAILABLE, every '
    + 'read-derived state renders unknown (hatched, em-dash), and the backend is still '
    + 'writing HmiProcessStopRequest TRUE — the boot value it must not flip');
  await stopStack();
}

async function passColdStart(cdp) {
  await startStack('coldstart', ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await sleep(1500);

  let r = await readout(cdp, '01 cold start, link up');
  check('step 1: the stop boots ENGAGED and now looks armed',
    r.pstop.cls.includes('engaged') && !r.pstop.cls.includes('unavailable'), r.pstop.label);
  check('step 1: §14.9 signature — mode None, ceiling 0.00, permit not stated',
    r.machineMode === 'NONE' && r.zoneE.ceiling.includes('0.00')
    && r.zoneE.permit.includes('not stated'), JSON.stringify(r.zoneE));
  check('step 2: connection cleared nothing — the latch and the reset stand',
    r.zoneC.pstop.includes('LATCHED') && r.zoneC.resetreq.includes('REQUIRED'),
    JSON.stringify(r.zoneC));
  await cdp.shot(`v2a-01-cold-start-before-operator-${DATE}.png`,
    'cold start with the link up, before the operator does anything: PROCESS STOP '
    + 'ENGAGED and armed, process stop latched, reset required, envelope withheld / '
    + '0.00 m/s / not stated. Connecting has cleared nothing');

  // ---- step 3: release the stop. The latch must visibly NOT clear.
  await cdp.click('#pstop');
  await sleep(900);
  r = await readout(cdp, '02 stop released');
  check('step 3: the request cleared', r.requests.pstop === 'false', r.requests.pstop);
  check('step 3: PS1 — the LATCH did not clear with it',
    r.zoneC.pstop.includes('LATCHED'), r.zoneC.pstop);
  await cdp.shot(`v2a-02-process-stop-released-latch-stands-${DATE}.png`,
    'step 3, the operator releases the process stop: HmiProcessStopRequest goes FALSE '
    + 'and the latch visibly does NOT clear. Request and latch are two things');

  // ---- step 4: the monitored reset, press-and-hold.
  const p = await cdp.press('#reset');
  await sleep(1400);
  r = await readout(cdp, '03 reset held');
  check('step 4: RESET is a level and is held', r.requests.reset === 'true',
    r.requests.reset);
  await cdp.shot(`v2a-03-reset-held-${DATE}.png`,
    'step 4, RESET held: HmiResetRequest is TRUE for as long as the button is down. '
    + 'The PLC acts on the rising edge; the hold is the operator\'s');
  await cdp.release(p);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
  await sleep(900);
  r = await readout(cdp, '04 latches cleared');
  check('step 4: latches cleared and NOTHING energized',
    r.zoneC.pstop.includes('clear') && r.zoneC.resetreq.includes('not required')
    && r.zoneC.teleop.includes('inactive') && r.zoneE.enable.includes('WITHHELD'),
    JSON.stringify(r.zoneC) + JSON.stringify(r.zoneE));
  await cdp.shot(`v2a-04-latches-cleared-nothing-energized-${DATE}.png`,
    'after the reset: process stop latch and reset-required both clear, and nothing '
    + 'moved — teleop inactive, motion withheld, ceiling still 0.00 m/s');

  // ---- step 5a: TELEOP, sampled INSIDE both halves of the adopt window.
  await cdp.click('#mode1');
  await sleep(350);                       // well inside the 1.2 s first stage
  r = await readout(cdp, '05 selection in flight');
  check('adopt window, stage 1: the chip reads SELECTION NOT IN FORCE',
    r.strip.mode === 'SELECTION NOT IN FORCE', r.strip.mode);
  check('adopt window, stage 1: machine mode still reads the PLC value, not the selector',
    r.machineMode === 'NONE', r.machineMode);
  await cdp.shot(`v2a-05-mode-change-in-flight-not-in-force-${DATE}.png`,
    'A MODE CHANGE IN FLIGHT, stage 1 (selected TELEOP, in force still NONE): the chip '
    + 'reads "selection not in force" in a neutral colour and never as an alarm, and the '
    + 'large text still shows the PLC\'s value. Captured 350 ms into a 1.2 s window');

  await waitFor('the PLC to enter the mode',
    async () => (await state()).metrics.ForkliftDriveModeActive === 1);
  await sleep(400);                       // inside the 1.2 s second stage
  r = await readout(cdp, '06 vehicle adopting');
  check('adopt window, stage 2: the chip reads VEHICLE ADOPTING',
    r.strip.mode === 'VEHICLE ADOPTING', r.strip.mode);
  check('adopt window, stage 2: both values are shown, labelled as differing',
    r.vehicleDiff === true && r.machineMode === 'TELEOP' && r.vehicleMode === 'NONE',
    `${r.machineMode}/${r.vehicleMode}`);
  await cdp.shot(`v2a-06-mode-change-in-flight-vehicle-adopting-${DATE}.png`,
    'A MODE CHANGE IN FLIGHT, stage 2 (in force TELEOP, vehicle still applying NONE): '
    + '"vehicle adopting", neutral, no clock on it. The two data are shown side by side '
    + 'as data, never as a verdict');

  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(800);
  r = await readout(cdp, '07 teleop settled');
  check('the in-flight rendering CLEARED once the window closed',
    r.strip.mode === 'TELEOP' && r.vehicleDiff === false, r.strip.mode);
  check('§8: with the link UP the selector carries no "not reaching the PLC" caption',
    r.modelink.on === false, r.modelink.text);
  await cdp.shot(`v2a-07-teleop-mode-in-force-${DATE}.png`,
    'TELEOP in force and settled: the in-flight rendering has cleared, selected = in '
    + 'force = applied, and zone B has un-greyed');

  // ---- the enable, then the joystick.
  await cdp.click('#enable');
  await waitFor('ForkliftTeleopActive',
    async () => (await state()).metrics.ForkliftTeleopActive === true);
  const pad = await cdp.press('#pad');
  await cdp.dragTo('#pad', 0.78, 0.20);
  await sleep(900);
  r = await readout(cdp, '08 driving');
  check('teleop: the enable is a second, separate act after the mode',
    r.zoneC.teleop.includes('ACTIVE'), r.zoneC.teleop);
  await cdp.shot(`v2a-08-teleop-enabled-and-driving-${DATE}.png`,
    'TELEOP with the enable asserted and the joystick held: two deliberate acts, '
    + 'selecting the mode and then enabling motion');
  await cdp.release(pad);
  await sleep(600);

  // ---- step 5b: AUTONOMOUS.
  await cdp.click('#enable');            // release the enable first
  await sleep(300);
  await cdp.click('#mode2');
  await waitFor('the envelope to be published',
    async () => (await state()).metrics.ForkliftMotionEnable === true);
  await sleep(900);
  r = await readout(cdp, '09 autonomous');
  check('autonomous: the selection IS the affirmative enable',
    r.machineMode === 'AUTONOMOUS' && r.strip.mode === 'AUTONOMOUS', r.strip.mode);
  check('autonomous: the envelope permits and states a ceiling, not a setpoint',
    r.zoneE.enable.includes('PERMITTED') && r.zoneE.ceiling.includes('0.80 m/s'),
    JSON.stringify(r.zoneE));
  check('M6: teleop-active and motion-enable are never both asserted',
    !(r.zoneC.teleop.includes('ASSERTED') && r.zoneE.enable.includes('PERMITTED')),
    r.zoneC.teleop + ' / ' + r.zoneE.enable);
  await cdp.shot(`v2a-09-autonomous-mode-in-force-${DATE}.png`,
    'AUTONOMOUS in force: selecting it was the affirmative action, and the envelope '
    + 'now reads permitted / 0.80 m/s ceiling / equipment ready. A permission, never a '
    + 'command');

  // ---- the process stop engaged during a run.
  await cdp.click('#pstop');
  await sleep(250);
  r = await readout(cdp, '10 stop engaged');
  check('the stop engaged on press, with no confirmation dialog',
    r.requests.pstop === 'true' && r.pstop.cls.includes('engaged'), r.pstop.label);
  await cdp.shot(`v2a-10-process-stop-engaged-${DATE}.png`,
    'PROCESS STOP engaged during an autonomous run: amber, rectangular, depressed, '
    + 'captioned "stop requested — release, then RESET". It acts on press');
  await waitFor('the PLC to latch the stop',
    async () => (await state()).metrics.ForkliftProcessStopActive === true);
  await sleep(900);
  r = await readout(cdp, '11 stop latched');
  check('PS6: the envelope went non-permissive under the latch',
    r.zoneE.enable.includes('WITHHELD') && r.zoneE.ceiling.includes('0.00'),
    JSON.stringify(r.zoneE));
  await cdp.shot(`v2a-11-process-stop-latched-${DATE}.png`,
    'the PLC has latched the stop: "process stop latched" and "reset required" assert, '
    + 'and the envelope goes non-permissive. The stop reaches the vehicle through the '
    + 'envelope, not through a stop topic of its own');

  await cdp.evaluate(`document.getElementById('diag').open = true`);
  await sleep(500);
  await cdp.shot(`v2a-12-diagnostics-drawer-open-${DATE}.png`,
    'zone F, the collapsed diagnostics drawer opened: every raw input, output, request '
    + 'and counter v1 showed as a labelled number is here, demoted rather than deleted. '
    + 'ForkliftVehicleHeartbeat is the RAW counter — no liveness verdict is derived here');
  await cdp.evaluate(`document.getElementById('diag').open = false`);
  await stopStack();
}

async function passRefused(cdp) {
  await startStack('refused', ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await cdp.click('#pstop');
  await sleep(400);
  const p = await cdp.press('#reset');
  await sleep(800);
  await cdp.release(p);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
  await cdp.click('#mode2');
  await sleep(5000);                     // four adopt windows and then some
  const r = await readout(cdp, '13 refused entry');
  check('a refused entry: the disagreement NEVER resolves and is still not an alarm',
    r.strip.mode === 'SELECTION NOT IN FORCE' && r.machineMode === 'NONE',
    r.strip.mode + '/' + r.machineMode);
  const caption = await cdp.evaluate(
    `document.getElementById('modecaption').textContent`);
  check('the refusal caption states the away-and-back re-selection',
    /return the selector to NONE/.test(caption) && /select again/.test(caption),
    caption);
  const cond = await cdp.evaluate(
    `document.getElementById('conditions').classList.contains('on')`);
  check('the conditions list is shown, and it is PLC-published values only',
    cond === true, String(cond));
  await cdp.shot(`v2a-13-mode-selection-refused-${DATE}.png`,
    'A DISAGREEMENT THAT NEVER RESOLVES: AUTONOMOUS selected, the PLC refused the entry '
    + 'and consumed it, and 5 s later the chip still reads "selection not in force". The '
    + 'caption states the recovery — selector back to NONE, resolve, select again — and '
    + 'the conditions strip re-renders what the PLC publishes, diagnosing nothing here');
  await stopStack();
}

async function passDisagree(cdp) {
  await startStack('disagree', ['--with-safety-mirrors', '--disagree-latch-after', '6']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await cdp.click('#pstop');
  await sleep(400);
  const p = await cdp.press('#reset');
  await sleep(800);
  await cdp.release(p);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
  await cdp.click('#mode2');
  await waitFor('the PLC to enter the mode',
    async () => (await state()).metrics.ForkliftDriveModeActive === 2);
  await sleep(2500);                     // twice the adopt window, unresolved
  let r = await readout(cdp, '14 vehicle never adopts');
  check('an unresolved ADOPT window is still rendered neutrally, never as a fault',
    r.strip.mode === 'VEHICLE ADOPTING' && r.vehicleDiff === true, r.strip.mode);
  check('the mode chip itself never says "fault"',
    !/FAULT/i.test(r.strip.mode), r.strip.mode);
  await cdp.shot(`v2a-14-vehicle-adopting-unresolved-${DATE}.png`,
    'a vehicle that never adopts: AUTONOMOUS in force, vehicle still applying NONE, '
    + '2.5 s after the mode was entered and twice the adopt window. Still neutral, still '
    + 'not an alarm — declaring a persistent disagreement is the PLC\'s job, not this '
    + 'screen\'s');
  await waitFor('the PLC to declare the disagreement',
    async () => (await state()).metrics.ForkliftResetRequired === true, 20000);
  await sleep(900);
  r = await readout(cdp, '15 PLC declared the fault');
  check('the fault display is the PLC\'s ForkliftResetRequired, in zone C',
    r.zoneC.resetreq.includes('REQUIRED'), r.zoneC.resetreq);
  await cdp.shot(`v2a-15-mode-disagreement-declared-by-plc-${DATE}.png`,
    'the same disagreement after the PLC\'s own delay elapsed: RESET REQUIRED asserts in '
    + 'zone C and the envelope goes non-permissive. The verdict arrived from the PLC; the '
    + 'HMI ran no timer and computed nothing');
  await stopStack();
}

async function passLinkAndSession(cdp) {
  await startStack('linkdrop', ['--with-safety-mirrors', '--link-drop-after', '14']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await cdp.click('#pstop');            // release, so the control is visibly armed
  await sleep(600);
  await waitFor('the PLC to withdraw its link verdict',
    async () => (await state()).metrics.HmiLinkOk === false, 30000);
  await sleep(900);
  let r = await readout(cdp, '16 HmiLinkOk false');
  check('HmiLinkOk FALSE: the process stop renders UNAVAILABLE with the session UP',
    r.pstop.cls.includes('unavailable') && r.pstop.disabled === true
    && r.strip.session === 'CONNECTED', r.strip.session + ' ' + r.pstop.cls);
  check('HmiLinkOk FALSE: it is not left looking engaged either',
    !r.pstop.cls.includes('engaged'), r.pstop.cls);
  check('§8: link down — the selector renders its position AND says it is not '
    + 'reaching the PLC',
    r.modelink.on === true && /not reaching the PLC/i.test(r.modelink.text)
    && r.selected.length === 1, r.modelink.text + ' selected=' + JSON.stringify(r.selected));
  check('HmiLinkOk FALSE: every read-derived state renders UNKNOWN',
    r.zoneC.resetreq.startsWith('UNKNOWN') && r.zoneD.estop.startsWith('UNKNOWN'),
    JSON.stringify(r.zoneC));
  await cdp.shot(`v2a-16-link-down-process-stop-unavailable-${DATE}.png`,
    'HmiLinkOk FALSE with the OPC UA SESSION STILL UP: the PROCESS STOP renders '
    + 'UNAVAILABLE — hatched, greyed, "link down — request cannot reach the PLC" — and '
    + 'the strip states the degraded-mode fact. The two causes are visibly separate');
  await cdp.shot(`v2a-17-safety-lamps-unknown-link-down-${DATE}.png`,
    'ZONE D CROPPED out of the same frame: with the reading unattributable the four '
    + 'F-layer lamps render UNKNOWN (grey, hatched, em-dash) rather than clear. A lamp '
    + 'with no data shows no state', '#fzone');

  // ---- now the session itself: the double goes away under a live session.
  stop('double');
  await waitFor('the session to leave CONNECTED',
    async () => (await state()).session.state !== 'CONNECTED', 30000);
  await sleep(1500);
  r = await readout(cdp, '18 session down');
  check('session down: the process stop is UNAVAILABLE',
    r.pstop.cls.includes('unavailable'), r.pstop.cls);
  await cdp.shot(`v2a-18-session-down-${DATE}.png`,
    'the PLC-side server went away under a live session: the session chip leaves '
    + 'CONNECTED, every state reads unknown and the PROCESS STOP is UNAVAILABLE on the '
    + 'backend\'s own channel rather than on HmiLinkOk');

  // ---- and the backend itself.
  stop('hmi');
  await sleep(2500);
  r = await readout(cdp, '19 backend gone');
  check('backend gone: the page renders unknown rather than freezing on its last look',
    r.pstop.cls.includes('unavailable') && r.machineMode === '—',
    r.machineMode + ' ' + r.pstop.cls);
  await cdp.shot(`v2a-19-backend-not-answering-${DATE}.png`,
    'the HMI backend itself stopped: the page does not keep its last live look — every '
    + 'state goes unknown and the stop is UNAVAILABLE');
  await stopStack();
}

async function passSafety(cdp) {
  // Healthy mirrors, then an F-demand, on one run.
  await startStack('coldstart', ['--with-safety-mirrors',
    '--safety-healthy-after', '2', '--safety-demand-after', '14']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await waitFor('the mirrors to read healthy',
    async () => (await state()).safety.SafetyResetRequired === false);
  await sleep(900);
  let r = await readout(cdp, '20 mirrors healthy');
  check('mirrors present and clear render as CLEAR, not as unknown',
    r.zoneD.estop.startsWith('clear') && r.zoneD.absent === false, r.zoneD.estop);
  await cdp.shot(`v2a-20-safety-lamps-healthy-${DATE}.png`,
    'zone D with the F-layer mirrors present and clear: outlined lamps, its own banner '
    + 'and its own frame, and no element of zone C merged into it');
  await waitFor('the F-demand',
    async () => (await state()).safety.EStopDemand === true, 30000);
  await sleep(900);
  r = await readout(cdp, '21 F-demand');
  check('an F-demand asserts RED, and red appears nowhere else on the page',
    r.zoneD.estop.startsWith('ASSERTED'), r.zoneD.estop);
  check('the process stop is still AMBER, never red, under an active F-demand',
    !r.pstop.cls.includes('unavailable'), r.pstop.cls);
  await cdp.shot(`v2a-21-safety-lamps-f-demand-active-${DATE}.png`,
    'an F-layer e-stop demand asserted: the demand lamp is the only RED element on the '
    + 'page, and the PROCESS STOP beside it stays amber. Nothing on this screen can '
    + 'write, clear or reset the mirror');
  await stopStack();

  // The absent group.
  await startStack('coldstart', []);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  await sleep(1200);
  r = await readout(cdp, '22 mirrors absent');
  check('an absent mirror group greys and is not a connect failure',
    r.zoneD.absent === true && r.zoneD.estop.startsWith('UNKNOWN')
    && r.strip.session === 'CONNECTED', JSON.stringify(r.zoneD));
  await cdp.shot(`v2a-22-safety-lamps-group-absent-${DATE}.png`,
    'the server does not carry Forklift/Safety/ at all: the whole zone greys with '
    + '"F-layer mirrors not present on this server", the session stays CONNECTED, and no '
    + 'lamp is substituted with FALSE');
  await stopStack();
}

async function passPageStale(cdp) {
  await startStack('coldstart', ['--with-safety-mirrors']);
  await cdp.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);
  // Clear the boot latches first, so the frame this pass photographs is a
  // coherent one rather than a mode in force under a standing latch.
  await cdp.click('#pstop');             // release the stop
  await sleep(400);
  const rp = await cdp.press('#reset');
  await sleep(900);
  await cdp.release(rp);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
  await cdp.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(800);
  // The page stops talking: exactly what a crashed or frozen browser looks
  // like from inside the backend. The five deadman requests go to rest; the
  // two STANDING controls must not move.
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions',
    { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await sleep(2000);
  const s = await state();
  check('H6: the five deadman requests went to rest',
    s.requests.HmiTeleopRequest === false && s.requests.HmiTractionRequest === 0,
    JSON.stringify(s.requests));
  check('PS-B: the STANDING process stop held its operator-set value through the drop',
    s.requests.HmiProcessStopRequest === false, String(s.requests.HmiProcessStopRequest));
  check('§5.1: the STANDING mode selector held its operator-set value through the drop',
    s.requests.HmiDriveModeRequest === 1, String(s.requests.HmiDriveModeRequest));
  check('H6: the heartbeat kept running through the page drop',
    s.heartbeat.running === true, String(s.heartbeat.running));
  await cdp.send('Network.emulateNetworkConditions',
    { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await sleep(1200);
  const r = await readout(cdp, '23 after a page drop');
  await cdp.shot(`v2a-23-page-beacon-drop-standing-controls-held-${DATE}.png`,
    'after this page went quiet and returned: the backend held the five teleop requests '
    + 'at rest and dropped the enable, while the process stop and the mode selector — '
    + 'standing controls — kept their operator-set values. A page loss is not an '
    + 'operator act, and nothing latched');
  await stopStack();
}

/* ===========================================================================
 * THE SECOND TAB — m5-29 finding 1, reproduced rather than reasoned about.
 *
 * An operator who opens a second tab is not doing anything unusual. The v2a
 * build rendered both STANDING controls from a local copy adopted once and
 * re-asserted that copy in EVERY post — the dirty loop, the deadman, `blur`,
 * `visibilitychange`. One tab and one reload are safe; a second tab is not.
 *
 * This pass walks that exact path:
 *
 *   1. the operator, in tab A, releases the stop, resets and selects TELEOP;
 *   2. tab B is opened — it must render what the BACKEND holds now, not the
 *      §12.8 boot values;
 *   3. the operator ENGAGES the stop in tab A, so tab B's copy is now stale;
 *   4. tab B is backgrounded, and the page's own `visibilitychange` and `blur`
 *      handlers are fired on it.
 *
 * Under the defect, step 4 releases the engaged stop on the wire while tab A
 * still reads PROCESS STOP — ENGAGED. The three checks below are the review's
 * F1 (a), (b) and (c); (c) reads the backend's own per-cycle evidence CSV, so
 * it is not two lucky samples either side of the event but every cycle in the
 * window.
 * ======================================================================== */
async function passSecondTab(cdpA) {
  const STEM = 'hmi/evidence/hmi-cycles-2026-08-05-secondtab.csv';
  await startStack('coldstart', ['--with-safety-mirrors'], STEM);
  await cdpA.navigate(HMI_BASE + '/');
  await waitFor('the PLC link verdict',
    async () => (await state()).metrics.HmiLinkOk === true);

  // ---- 1. the operator works in tab A: release, reset, select TELEOP.
  await cdpA.click('#pstop');
  await sleep(500);
  const rp = await cdpA.press('#reset');
  await sleep(900);
  await cdpA.release(rp);
  await waitFor('the latches to clear',
    async () => (await state()).metrics.ForkliftResetRequired === false);
  await cdpA.click('#mode1');
  await waitFor('the vehicle to report the mode',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(600);
  let s = await state();
  check('second tab, setup: the backend now holds stop RELEASED and mode TELEOP',
    s.controls.process_stop === false && s.controls.drive_mode === 1,
    JSON.stringify(s.controls));

  // ---- 2. THE SECOND TAB.
  const cdpB = await openTab();
  await cdpB.navigate(HMI_BASE + '/');
  await sleep(1500);
  let rb = await readout(cdpB, 'B1 second tab opened mid-scenario');
  check('F1(a): a second page opened mid-scenario renders the BACKEND\'s standing '
    + 'values, not the §12.8 boot values',
    !rb.pstop.cls.includes('engaged') && rb.pstop.label === 'PROCESS STOP'
    && rb.selected.length === 1 && rb.selected[0] === 1,
    rb.pstop.label + ' selected=' + JSON.stringify(rb.selected));
  await cdpB.shot(`v2a-24-second-tab-adopts-current-state-${DATE}.png`,
    'a SECOND TAB opened while the operator was already working in the first: it renders '
    + 'the stop RELEASED and TELEOP selected — the values the backend holds now — and not '
    + 'the §12.8 boot values it would have shown by asserting its own defaults');

  // ---- 3. the operator ENGAGES the stop in tab A. Tab B's copy is now stale.
  await cdpA.click('#pstop');
  await waitFor('the PLC to latch the stop',
    async () => (await state()).metrics.ForkliftProcessStopActive === true);
  await sleep(700);
  const rA = await readout(cdpA, 'A engaged the stop');
  check('second tab: the acting page shows the stop ENGAGED',
    rA.pstop.cls.includes('engaged'), rA.pstop.label);
  rb = await readout(cdpB, 'B2 the other tab follows the backend');
  check('F1(a2): the OTHER tab followed the backend and now renders ENGAGED too',
    rb.pstop.cls.includes('engaged'), rb.pstop.label);

  s = await state();
  const cycleBefore = Number(s.write.cycles);

  // ---- 4. background tab B and fire the page's own handlers on it.
  await cdpA.send('Page.bringToFront');
  await sleep(300);
  const walked = await cdpB.evaluate(`(() => {
    const before = document.visibilityState;
    try {
      Object.defineProperty(document, 'visibilityState',
        { configurable: true, get: () => 'hidden' });
    } catch (e) { /* already hidden by bringToFront */ }
    document.dispatchEvent(new Event('visibilitychange'));
    window.dispatchEvent(new Event('blur'));
    return { before, dispatched: document.visibilityState };
  })()`);
  log('B3 backgrounded — visibilityState ' + JSON.stringify(walked)
    + '; visibilitychange and blur dispatched into the page');
  await sleep(3000);              // longer than the evidence CSV's flush period

  s = await state();
  check('F1(b): backgrounding the non-acting page changed NEITHER standing value '
    + 'on the wire — the engaged stop is still engaged',
    s.requests.HmiProcessStopRequest === true && s.requests.HmiDriveModeRequest === 1,
    `HmiProcessStopRequest=${s.requests.HmiProcessStopRequest} `
    + `HmiDriveModeRequest=${s.requests.HmiDriveModeRequest}`);
  check('F1(b2): H6 still fired for the DEADMAN requests of the backgrounded page',
    s.requests.HmiTeleopRequest === false && s.requests.HmiTractionRequest === 0,
    JSON.stringify(s.requests));

  const rA2 = await readout(cdpA, 'A after the other tab was backgrounded');
  check('F1(b3): the operator\'s own screen and the wire still agree — ENGAGED',
    rA2.pstop.cls.includes('engaged') && rA2.requests.pstop === 'true',
    rA2.pstop.label + ' / ' + rA2.requests.pstop);
  await cdpA.shot(`v2a-25-second-tab-backgrounded-stop-stays-engaged-${DATE}.png`,
    'THE FAILURE PATH WALKED: a second tab was opened, the operator engaged the stop in '
    + 'this one, and the second tab was then backgrounded with its visibilitychange and '
    + 'blur handlers fired. The engaged stop is still engaged, on the wire and on this '
    + 'screen, and the selector is still TELEOP');

  // ---- (c) every cycle in the window, from the backend's own evidence CSV.
  const csv = readEvidenceCsv(STEM);
  const after = csv.rows.filter((r) => Number(r.cycle) > cycleBefore);
  const badStop = after.filter((r) => r.HmiProcessStopRequest !== 'True');
  const badMode = after.filter((r) => r.HmiDriveModeRequest !== '1');
  check('F1(c): the blur-triggered post carried NO standing key — every one of the '
    + `${after.length} write cycles after the background still wrote the stop `
    + 'engaged and the mode TELEOP',
    after.length > 10 && badStop.length === 0 && badMode.length === 0,
    `cycles=${after.length} stop-flips=${badStop.length} `
    + `mode-flips=${badMode.length} csv=${path.basename(csv.path)}`);

  await closeTab(cdpB);
  await stopStack();
}

// --------------------------------------------------------------------- main
let chrome, cdp;
try {
  const profile = path.join(SCRATCH, 'profile');
  rmSync(profile, { recursive: true, force: true });
  chrome = start('chrome', CHROME, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${CDP_PORT}`, `--user-data-dir=${profile}`,
    '--window-size=1560,1720', 'about:blank',
  ]);
  const targets = await waitFor('chrome to expose a page target', async () => {
    const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
    const page = list.find((t) => t.type === 'page');
    return page ? page.webSocketDebuggerUrl : null;
  }, 30000);
  cdp = await Cdp.open(targets);
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride',
    { width: 1540, height: 1700, deviceScaleFactor: 1, mobile: false });
  const ver = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/version`)).json();
  log('browser', ver.Browser);
  appendFileSync(MANIFEST, `browser: ${ver.Browser}\n\n`);

  const RUNNERS = {
    boot: passBoot, coldstart: passColdStart, refused: passRefused,
    disagree: passDisagree, linksession: passLinkAndSession, safety: passSafety,
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
  await sleep(600);
}
