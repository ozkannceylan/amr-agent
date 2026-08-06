/*
 * TEST HARNESS — HMI v2b, the map pane, against the REAL monitoring service
 * and a REAL vehicle.
 *
 *     #############################################################
 *     #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
 *     #############################################################
 *
 * A NEW FILE, AND EVERY OUTPUT IT WRITES IS NAMED `v2b-real-*`.
 * `capture_v2b_screens.mjs` and its `v2b-*` captures are the DOUBLE's evidence:
 * they are what this run is measured against, and a repeat that reuses its
 * predecessor's names destroys the comparison it exists to make
 * (docs/LESSONS.md 2026-08-06). Nothing here overwrites anything there, and a
 * reader can tell a real-service capture from the double's by the file name
 * alone.
 *
 * WHAT IS REAL HERE AND WHAT IS NOT — stated first, because a run that blurs
 * this is worth nothing:
 *
 *     viz/monitor/service.py   REAL, in WSL, subscribe-only in domain 51
 *     the vehicle              REAL: Gazebo + the forklift image + Nav2, WSL
 *     the map, pose, scan      REAL, from that vehicle's own ROS 2 graph
 *     hmi_server.py            the software under test, Windows
 *     the browser here         plays the OPERATOR, through the page
 *     v2a_scenario_double.py   STILL A DOUBLE. It plays the PLC, because the
 *                              controller is not available to this session.
 *                              Zones A-F are therefore rehearsed, not proven,
 *                              and only the MAP PANE is joined to reality
 *
 * THE CROSSING, which is the whole point of the run. The monitoring service
 * needs rclpy and runs in WSL; this page and its backend run on Windows. WSL2
 * relays the Windows loopback address to a Linux service bound to 127.0.0.1,
 * so `http://127.0.0.1:8089` on Windows reaches it with NO change to either
 * layer — the HMI's loopback rule (invariant 8) is satisfied on the address it
 * already had. See hmi/EVIDENCE_HMI.md section K for the proof and the
 * conditions it depends on.
 *
 * THE STALE PASS IS THE POINT, AND HERE IT IS NOT SIMULATED. The double could
 * only be told to stop publishing. This run stops COMMANDING THE VEHICLE and
 * lets a genuinely standing forklift produce the residual by itself: AMCL
 * publishes only on a filter update, so the pose stream simply ends. The pass
 * asserts at the PIXEL level that the solid marker is gone.
 *
 * Run (from the repository root, with the vehicle and viz already up in WSL):
 *     node hmi/tools/capture_v2b_real_screens.mjs
 *     node hmi/tools/capture_v2b_real_screens.mjs --passes reallive,realstale
 */

import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync, appendFileSync, openSync, statSync, rmSync }
  from 'node:fs';
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
const CDP_PORT = parseInt(arg('cdp-port', '9336'), 10);
// The endpoint `config-v2b-double.yaml` names. It is not overridable on the
// backend's command line, so the double must come up on exactly this port.
const OPCUA_PORT = arg('opcua-port', '4862');
const HMI_PORT = arg('hmi-port', '8098');
const VIZ_PORT = arg('viz-port', '8089');          // the REAL service, in WSL
const SERIAL = arg('serial', 'F001');
const HMI_BASE = `http://127.0.0.1:${HMI_PORT}`;
const VIZ_BASE = `http://127.0.0.1:${VIZ_PORT}`;
const DRIVE = arg('drive',
  '/mnt/c/Users/ozkan/AppData/Local/Temp/claude/'
  + 'C--Users-ozkan-projects-amr-agent/'
  + 'b8b82e36-4ca6-4a60-b4a7-22454f63880f/scratchpad/drive_f001.py');
const SCRATCH = path.join(os.tmpdir(), 'amr-hmi-v2b-real-screens');

const ALL_PASSES = ['reallive', 'realstale', 'realdown'];
const PASSES = arg('passes', ALL_PASSES.join(',')).split(',').map((s) => s.trim());

mkdirSync(OUT, { recursive: true });
mkdirSync(SCRATCH, { recursive: true });
const MANIFEST = path.join(OUT, `MANIFEST-v2b-real-${DATE}.txt`);
writeFileSync(MANIFEST,
  `HMI v2b map pane — REAL monitoring service, REAL vehicle — ${DATE}\n`
  + `produced by hmi/tools/capture_v2b_real_screens.mjs against\n`
  + `  viz/monitor/service.py   THE REAL SERVICE, in WSL, domain ${SERIAL}\n`
  + `  a real Gazebo forklift with Nav2 and AMCL\n`
  + `  hmi/tools/v2a_scenario_double.py  STILL A DOUBLE — it plays the PLC\n\n`);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function log(...m) { console.log('[capture-real]', ...m); }

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

// -------------------------------------------------------------- the WSL side
/** Run one command in WSL and return its stdout. The vehicle, the monitoring
 *  service and the motion stimulus all live there; this instrument only ever
 *  starts and stops them, and never reaches into a ROS 2 graph itself. */
function wsl(command, timeoutMs = 120000) {
  const r = spawnSync('wsl.exe', ['-e', 'bash', '-lc', command],
    { encoding: 'utf8', timeout: timeoutMs });
  return (r.stdout || '') + (r.stderr || '');
}
function vizPids() {
  return wsl("pgrep -f 'viz/monitor/service.py' || true")
    .split(/\s+/).filter((s) => /^\d+$/.test(s));
}
function vizStop() {
  const pids = vizPids();
  log(`stopping the REAL monitoring service, pid(s) ${pids.join(',') || 'none'}`);
  for (const p of pids) wsl(`kill ${p}`);
  return sleep(2500);
}
function vizStart() {
  wsl('cd /mnt/c/Users/ozkan/projects/amr-agent && source /opt/ros/jazzy/setup.bash'
    + ' && nohup python3 viz/monitor/service.py --status-period 10'
    + ' >> ~/m5-53b/viz.log 2>&1 & sleep 8; echo started');
  log('restarted the REAL monitoring service');
  return sleep(2000);
}
/** Command the vehicle to move, in the background, for `seconds`. The
 *  stimulus publishes its terminal zero and only then falls silent
 *  (docs/LESSONS.md 2026-08-04 #135). */
function driveFor(seconds, speed = 0.35, shuttle = 14) {
  wsl('cd /mnt/c/Users/ozkan/projects/amr-agent && source /opt/ros/jazzy/setup.bash'
    + ` && export ROS_DOMAIN_ID=51 && nohup python3 ${DRIVE} --speed ${speed}`
    + ` --steer 0.0 --shuttle ${shuttle} --seconds ${seconds}`
    + ' >> ~/m5-53b/drive-capture.log 2>&1 & sleep 1; echo driving');
  log(`commanded ${seconds} s of motion at ${speed} m/s`);
}

async function waitFor(what, fn, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch (e) { last = e.message; }
    await sleep(200);
  }
  throw new Error(`timed out waiting for ${what} (last: ${JSON.stringify(last)})`);
}
async function state() {
  return (await fetch(HMI_BASE + '/state', { cache: 'no-store' })).json();
}
async function monitor() {
  return (await fetch(HMI_BASE + '/monitor/state?serial=' + SERIAL,
    { cache: 'no-store' })).json();
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
  async navigate(url) { await this.send('Page.navigate', { url }); await sleep(1200); }
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

/** Zones A-F, read exactly as the double-fed harness reads them, so the two
 *  runs can be compared field for field. */
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
      pstop: {label: t('pstop'), cls: cls('pstop')},
      machineMode: t('machinemode'),
      zoneC: {pstop: stt('s_pstop'), resetreq: stt('s_resetreq'),
              teleop: stt('s_teleop')},
    };
  })()`);
  log(label, JSON.stringify(r));
  return r;
}

/** The map pane: DOM text plus a pixel census of the canvas, because the stale
 *  rendering is a drawing and not a caption. */
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

// ------------------------------------------------------------- the stack --
function startStack(scenario = 'coldstart') {
  start('double', PYTHON, ['hmi/tools/v2a_scenario_double.py',
    '--port', OPCUA_PORT, '--scenario', scenario, '--adopt-delay', '1.2',
    '--run-seconds', '900']);
  return sleep(3500).then(() => {
    start('hmi', PYTHON, ['hmi/hmi_server.py',
      '--config', 'hmi/config-v2b-double.yaml', '--http-port', HMI_PORT,
      '--monitor-url', VIZ_BASE]);
    return waitFor('the HMI backend to connect',
      async () => (await state()).session.state === 'CONNECTED');
  });
}
function stopStack() {
  stop('hmi'); stop('double');
  return sleep(1500);
}
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

// ---- 1. the real map, the real pose, the real returns ---------------------
async function passRealLive(cdp) {
  driveFor(150);
  await startStack();
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await cdp.click('#mode1');
  await waitFor('the vehicle mode to be reported',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);

  const ramp = (await monitor()).monitor;
  log(`display ramp published by the backend: ${ramp.age_ramp_start_ms} .. `
    + `${ramp.age_ramp_full_ms} ms; fetch of the real service ${ramp.fetch_ms} ms`);
  await waitFor('a pose FRESH enough to photograph, from the real localization',
    async () => {
      const s = (await monitor()).state;
      return s && s.pose_age_ms !== null && s.pose_age_ms < ramp.age_ramp_start_ms;
    }, 90000);
  await sleep(300);

  const m = await mapReadout(cdp, '00 REAL map, live pose, real returns');
  const raw = (await monitor()).state;
  check('the WHOLE map arrived from the REAL service and is painted',
    m.canvas.colours >= 3 && m.canvas.nonBlank > 10000
    && /whole map/.test(m.map), `${m.canvas.colours} colours, `
    + `${m.canvas.nonBlank} px, map row "${m.map}"`);
  check('the grid the page painted is the grid the vehicle published',
    raw.map_meta.width === 606 && raw.map_meta.height === 410
    && Math.abs(raw.map_meta.resolution_m - 0.05) < 1e-6,
    JSON.stringify(raw.map_meta));
  check('the LIVE pose is drawn solid, from the vehicle\'s own AMCL',
    m.canvas.vehicleFill > 8, `${m.canvas.vehicleFill} px at the marker fill colour`);
  check('the pose carries its AGE and is never called live',
    /as of /.test(m.pose) && !/LAST KNOWN/.test(m.pose) && !/live/i.test(m.pose),
    m.pose);
  check('REAL lidar returns are drawn as obstacles, in the three classes the '
    + 'sensor reported', m.canvas.obstacleInk > 20
    && /distance returns/.test(m.obstacles) && /beyond range/.test(m.obstacles),
    m.obstacles);
  check('the returns were placed in the map frame by the VEHICLE\'s own TF',
    raw.obstacles.placed === true && raw.obstacles.frame === 'map',
    `placed=${raw.obstacles && raw.obstacles.placed} frame=${raw.obstacles
      && raw.obstacles.frame}`);
  check('the obstacle row still makes no verdict',
    !/(clear|safe|danger|near)/i.test(m.obstacles.replace(/beyond range/g, '')),
    m.obstacles);
  check('the serial roots the pane, and it is the allocation table\'s',
    m.serial === SERIAL, m.serial);

  await cdp.shot(`v2b-real-00-map-live-real-service-${DATE}.png`,
    'THE REAL THING: the whole occupancy grid, the live pose and the lidar returns '
    + `have all arrived from viz/monitor/service.py subscribing in ${SERIAL}'s own `
    + `DDS domain, across the WSL-to-Windows loopback relay. Pose age at capture `
    + `${raw.pose_age_ms.toFixed(0)} ms, ${raw.obstacles.returns.distance} distance `
    + 'returns. Every row carries the age of the datum it came from', '#mapzone');
  await cdp.shot(`v2b-real-01-whole-page-real-service-${DATE}.png`,
    'the whole operator page on real monitoring data. Zones A-F are driven by a PLC '
    + 'DOUBLE and are rehearsed, not proven; only the map pane is joined to a real '
    + 'vehicle, and no caption merges a value from one plane with a value from the other');

  // A view transform is drawing. On real data as on the double's.
  const before = JSON.stringify((await state()).requests);
  await cdp.click('#mapin');
  await cdp.click('#mapin');
  await sleep(400);
  const after = JSON.stringify((await state()).requests);
  check('zooming the REAL map is drawing: not one written value moved',
    before === after, `${before} -> ${after}`);
  await cdp.shot(`v2b-real-02-map-zoomed-real-service-${DATE}.png`,
    'the same real map zoomed: a view transform derives no value, changes no datum '
    + 'and posts nothing', '#mapzone');
  await stopStack();
}

// ---- 2. THE STALE PATH, on a genuinely standing vehicle -------------------
async function passRealStale(cdp) {
  await startStack();
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);

  // Drive briefly so there is a FRESH sample to compare the stale one against,
  // then STOP COMMANDING and let the vehicle stand. Nothing is frozen, faked or
  // simulated: the pose stream ends because AMCL publishes only on a filter
  // update and a standing vehicle produces none.
  driveFor(30);
  const ramp = (await monitor()).monitor;
  await waitFor('a fresh pose while the vehicle is being driven',
    async () => {
      const s = (await monitor()).state;
      return s && s.pose_age_ms !== null && s.pose_age_ms < ramp.age_ramp_start_ms;
    }, 90000);
  await sleep(300);
  const fresh = await mapReadout(cdp, '03a driven — the baseline');
  check('the baseline is a SOLID marker while the vehicle is being driven',
    fresh.canvas.vehicleFill > 8 && !/LAST KNOWN/.test(fresh.pose),
    `${fresh.canvas.vehicleFill} px, "${fresh.pose}"`);
  await cdp.shot(`v2b-real-03-pose-fresh-while-driven-${DATE}.png`,
    `the baseline for the stale pass: the vehicle is under command and its pose is `
    + `${fresh.pose}. Solid marker, ${fresh.canvas.vehicleFill} px of fill`, '#mapzone');

  log('the stimulus is ending; the vehicle will now STAND. Nothing is frozen.');
  await waitFor('the pose age of a STANDING vehicle to cross the display ramp',
    async () => (await monitor()).state.pose_age_ms > ramp.age_ramp_full_ms + 4000,
    120000);
  await sleep(600);
  const m = await mapReadout(cdp, '03b STANDING — pose stale');
  const raw = (await monitor()).state;

  check('the marker has NO solid fill left — the picture changed, not the caption',
    fresh.canvas.vehicleFill > 8 && m.canvas.vehicleFill === 0,
    `${fresh.canvas.vehicleFill} px driven -> ${m.canvas.vehicleFill} px standing`);
  check('the readout says LAST KNOWN and gives the age',
    /LAST KNOWN/.test(m.pose) && /as of /.test(m.pose), m.pose);
  check('the banner says where the vehicle WAS, not where it is',
    m.staleBannerOn && /where the vehicle WAS/.test(m.staleBanner),
    m.staleBanner.slice(0, 90));
  check('the page does not guess between a standing vehicle and a stopped one',
    /does not guess/.test(m.staleBanner));
  check('THE OBSTACLE LAYER IS STILL FRESH at the same instant — the lidar keeps '
    + 'publishing while a standing vehicle produces no pose at all, and the two '
    + 'ages are independent',
    raw.obstacles_age_ms < 1000 && m.canvas.obstacleInk > 20,
    `obstacles ${raw.obstacles_age_ms} ms vs pose ${raw.pose_age_ms} ms`);
  check('the map itself is untouched by a stale pose',
    /whole map/.test(m.map), m.map);
  await cdp.shot(`v2b-real-04-pose-STALE-standing-vehicle-${DATE}.png`,
    `THE RESIDUAL THE DESIGN EXISTS FOR, ON REAL DATA: the forklift is STANDING, so `
    + `its localization has published nothing for ${(raw.pose_age_ms / 1000).toFixed(1)} s. `
    + 'Nothing was frozen and no staleness was simulated — the stimulus simply stopped. '
    + 'The marker is hollow with no fill, labelled LAST KNOWN POSITION with its age, and '
    + `the lidar layer beside it is still ${raw.obstacles_age_ms.toFixed(0)} ms old`,
    '#mapzone');
  await cdp.shot(`v2b-real-05-whole-page-pose-stale-standing-${DATE}.png`,
    'the same standing vehicle on the whole page: the process zones are unaffected, '
    + 'because the age of one plane says nothing about the other');
  await stopStack();
}

// ---- 3. the REAL monitoring service stopped mid-session -------------------
async function passRealDown(cdp) {
  await startStack();
  await cdp.navigate(HMI_BASE + '/');
  await clearLatches(cdp);
  await cdp.click('#mode1');
  await waitFor('the vehicle mode to be reported',
    async () => (await state()).metrics.ForkliftVehicleModeApplied === 1);
  await sleep(1200);
  const before = await readout(cdp, '05a zones A-F before the outage');
  const hbBefore = (await state()).heartbeat.value;
  const up = await monitor();
  check('the real service is answering before it is stopped',
    up.monitor.reachable === true, JSON.stringify(up.monitor.reason));

  await vizStop();
  await sleep(3500);

  const m = await mapReadout(cdp, '05b the REAL service stopped');
  const after = await readout(cdp, '05c zones A-F after the outage');
  const s = await state();
  check('the pane greys and says the service is not answering',
    m.messageOn && /not answering/.test(m.message), m.message.slice(0, 140));
  check('it shows NO last values — an unreachable source is not a source of last '
    + 'values', m.pose === '—' && m.obstacles === '—' && m.map === '—',
    `${m.pose} / ${m.obstacles} / ${m.map}`);
  check('nothing is left drawn on the canvas',
    m.canvas.vehicleFill === 0 && m.canvas.obstacleInk === 0,
    `${m.canvas.vehicleFill}/${m.canvas.obstacleInk}`);
  check('THE PROCESS PLANE IS UNTOUCHED: session still up, mode still in force',
    after.strip.session === 'CONNECTED' && after.machineMode === before.machineMode
    && after.zoneC.resetreq === before.zoneC.resetreq,
    `${after.strip.session} / ${after.machineMode}`);
  check('the heartbeat kept advancing across the outage',
    s.heartbeat.value !== hbBefore && s.heartbeat.running === true,
    `${hbBefore} -> ${s.heartbeat.value}`);
  check('the backend did not exit when its source died',
    s.session.state === 'CONNECTED', s.session.state);
  await cdp.shot(`v2b-real-06-real-monitoring-service-stopped-${DATE}.png`,
    'THE REAL MONITORING SERVICE STOPPED MID-SESSION: the map pane greys and says so — '
    + 'no map, no position, no obstacles, and no last values. The process zones beside '
    + 'it are unchanged and the heartbeat never paused. The vehicle is still running in '
    + 'its own domain; what died is the operator-side reader, and the HMI says exactly '
    + 'that');

  await vizStart();
  await waitFor('the pane to recover once the real service is back',
    async () => (await monitor()).monitor.reachable === true, 60000);
  await sleep(2500);
  const back = await mapReadout(cdp, '05d recovered');
  check('the pane recovers by itself when the real service returns',
    /whole map/.test(back.map) && back.canvas.nonBlank > 10000, back.map);
  await cdp.shot(`v2b-real-07-recovered-after-restart-${DATE}.png`,
    'the same page after the real monitoring service was restarted: the pane recovered '
    + 'on its own, refetched the whole grid and resumed. No operator action, and no '
    + 'reset of anything on the process plane', '#mapzone');
  await stopStack();
}

// --------------------------------------------------------------------- main
let chrome, cdp;
try {
  log(`checking the REAL monitoring service at ${VIZ_BASE}`);
  const probe = await fetch(VIZ_BASE + '/vehicles');
  const served = await probe.json();
  log(`the real service serves ${JSON.stringify(served.serials)} from `
    + `${served.allocation_table}`);
  appendFileSync(MANIFEST, `real service /vehicles: ${JSON.stringify(served)}\n`);
  if (!(served.serials || []).includes(SERIAL)) {
    throw new Error(`the real service does not serve ${SERIAL}`);
  }

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

  const RUNNERS = { reallive: passRealLive, realstale: passRealStale,
    realdown: passRealDown };
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
  console.error('[capture-real] FAILED', err);
  process.exitCode = 1;
} finally {
  stopAll();
  await sleep(800);
  try { cdp && cdp.ws.close(); } catch { /* already closed */ }
  await sleep(200);
  process.exit(process.exitCode || 0);
}
