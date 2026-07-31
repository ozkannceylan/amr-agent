/*
 * TEST HARNESS — the operator page in a real browser engine, screenshotted.
 *
 *     #############################################################
 *     #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
 *     #############################################################
 *
 * EVIDENCE_HMI.md section C loaded the page in Chromium and quoted values out
 * of the live DOM; it committed no image. This script is that pass again, run
 * end to end and recorded as PNGs, so the M4 page has a baseline a reader can
 * see before the HMI v2 work changes it.
 *
 * It presses the page's controls with genuine DOM pointer events — mouse down,
 * move and up — so the press-and-hold RESET and fork-jog handlers are the ones
 * exercised, not the HTTP endpoints behind them.
 *
 * Three roles, and the separation is the point (check_hmi_teleop_loop.py):
 *
 *     screens_plant_driver.py   plays the BRIDGE and the PLANT
 *     the browser here          plays the OPERATOR, through the page
 *     the double                plays the PLC. It owns every verdict
 *
 * Nothing observed here is evidence about the TIA Portal build, and nothing
 * here is part of the HMI: this file drives a browser and writes PNGs.
 *
 * Run (from the repository root):
 *     /opt/node22/bin/node hmi/tools/capture_screens.mjs \
 *         --out hmi/evidence --python ~/amr-hmi-venv/bin/python
 *
 * Requires a Chromium that Playwright can find (PLAYWRIGHT_BROWSERS_PATH) and
 * the Playwright package; both are environment tooling, not a dependency of
 * this layer — nothing in hmi/ imports either at run time.
 */

import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, openSync, statSync } from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
const PW = process.env.PLAYWRIGHT_MODULE || '/opt/node22/lib/node_modules/playwright';
const { chromium } = require(PW);

// ---------------------------------------------------------------- arguments
function arg(name, dflt) {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
}
const REPO = path.resolve(arg('repo', process.cwd()));
const OUT = path.resolve(arg('out', path.join(REPO, 'hmi/evidence')));
const PYTHON = arg('python', path.join(process.env.HOME || '/root', 'amr-hmi-venv/bin/python'));
const SCRATCH = arg('scratch', '/tmp/amr-hmi-screens');
const DATE = arg('date', new Date().toISOString().slice(0, 10));

mkdirSync(OUT, { recursive: true });
mkdirSync(SCRATCH, { recursive: true });

const PLANT_FILE = path.join(SCRATCH, 'plant.json');
const children = [];
const shots = [];

function log(...m) { console.log('[capture]', ...m); }

function start(name, cmd, args) {
  const out = openSync(path.join(SCRATCH, name + '.log'), 'a');
  const child = spawn(cmd, args, { cwd: REPO, stdio: ['ignore', out, out], detached: true });
  children.push({ name, child });
  log(`started ${name} pid ${child.pid}`);
  return child;
}

function stop(name) {
  for (const entry of children) {
    if (entry.name !== name || entry.child.killed) continue;
    try { process.kill(-entry.child.pid, 'SIGTERM'); } catch { /* already gone */ }
    entry.child.killed = true;
    log(`stopped ${name}`);
  }
}

function stopAll() { for (const e of children) stop(e.name); }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitFor(what, fn, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch (e) { last = e.message; }
    await sleep(200);
  }
  throw new Error(`timed out waiting for ${what} (last: ${last})`);
}

async function state(base) {
  const r = await fetch(base + '/state', { cache: 'no-store' });
  return r.json();
}

function plant(values) {
  writeFileSync(PLANT_FILE, JSON.stringify(values));
}

async function shot(page, file, caption, opts = {}) {
  const target = path.join(OUT, file);
  const el = opts.selector ? await page.locator(opts.selector) : null;
  if (el) await el.screenshot({ path: target });
  else await page.screenshot({ path: target, fullPage: true });
  const bytes = statSync(target).size;
  if (bytes < 3000) throw new Error(`${file} is only ${bytes} bytes — not a rendered page`);
  shots.push({ file, bytes, caption });
  log(`shot ${file}  ${bytes} bytes  — ${caption}`);
}

// A readable summary of what the page itself is showing, printed beside every
// screenshot so the image and the DOM it came from can be checked against each
// other later.
async function readout(page) {
  return page.evaluate(() => {
    const t = (id) => (document.getElementById(id) || {}).textContent;
    const on = (id) => (document.getElementById(id) || { classList: { contains: () => false } })
      .classList.contains('on');
    return {
      link: document.getElementById('link').className,
      linkstate: t('linkstate'), hb: t('hb'), rtt: t('rtt'), beacon: t('beacon'),
      lastwrite: t('lastwrite'),
      requests: {
        traction: t('q_traction'), steer: t('q_steer'), fork: t('q_fork'),
        teleop: t('q_teleop'), reset: t('q_reset'),
      },
      lamps: {
        teleop: on('l_teleop'), obstacle: on('l_obstacle'), speed: on('l_speed'),
        resetreq: on('l_resetreq'), linkok: on('l_linkok'), zone: on('l_zone'),
      },
      safety: {
        notpresent: document.getElementById('safety_lamps').classList.contains('notpresent'),
        estop: on('l_safety_estop'), zone: on('l_safety_zone'),
        resetreq: on('l_safety_resetreq'), resetfault: on('l_safety_resetfault'),
        banner: on('safetybanner'),
      },
      stopbanner: { on: on('stopbanner'), title: t('stoptitle') },
      metrics: {
        tref: t('m_tref'), speed: t('m_speed'), height: t('m_height'),
        dist: t('m_dist'), sref: t('m_sref'), fref: t('m_fref'),
        rtt: t('m_rtt'), rttmed: t('m_rttmed'), period: t('m_period'), age: t('m_age'),
      },
    };
  });
}

async function say(page, label) {
  const r = await readout(page);
  log(label, JSON.stringify(r));
  return r;
}

// -------------------------------------------------------------- pass A: logic double
async function passLogicDouble(browser) {
  plant({
    ForkliftForkHeight: 0.20, ForkliftLinearSpeed: 0.0,
    ForkliftObstacleInStopZone: false, ForkliftObstacleMinDistance: 3.50,
  });
  start('double', PYTHON, ['plc/forklift/double/server.py', '--port', '4850']);
  await sleep(3000);
  start('plant', PYTHON, ['hmi/tools/screens_plant_driver.py',
    '--commands', PLANT_FILE, '--run-seconds', '900']);
  start('hmi', PYTHON, ['hmi/hmi_server.py', '--config', 'hmi/config-logic-double.yaml']);

  const base = 'http://127.0.0.1:8090';
  await waitFor('the HMI backend', async () => (await state(base)).session.state === 'CONNECTED');

  const context = await browser.newContext({ viewport: { width: 1680, height: 1450 } });
  const page = await context.newPage();
  page.on('console', (m) => log('  console:', m.type(), m.text()));
  await page.goto(base + '/', { waitUntil: 'load' });
  await waitFor('the page to render a connected link',
    async () => (await page.locator('#linkstate').textContent()) === 'CONNECTED');
  await sleep(1200);

  // 1. Boot state: the double's ForkliftObstacleInStopZone start value is TRUE,
  //    so the PLC has a standing latch before the operator has touched anything.
  await say(page, 'boot');
  await shot(page, `hmi-page-01-reset-required-${DATE}.png`,
    'boot state against the logic double: RESET REQUIRED banner, ForkliftResetRequired lamp');

  // 2. The held RESET, pressed as an operator presses it (m4f-07b handlers).
  const reset = page.locator('#reset');
  const box = await reset.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await sleep(1500);
  await say(page, 'reset held');
  await shot(page, `hmi-page-02-reset-held-${DATE}.png`,
    'RESET held down: HmiResetRequest true for as long as the button is held');
  await sleep(800);
  await page.mouse.up();
  await sleep(800);
  const cleared = await waitFor('the latch to clear',
    async () => (await state(base)).metrics.ForkliftResetRequired === false, 8000);
  log('ForkliftResetRequired after the held reset:', cleared);

  // 3. Connected and driving. The carriage is raised past the slow threshold so
  //    the PLC's own speed cap is the thing the lamp reports.
  plant({
    ForkliftForkHeight: 1.20, ForkliftLinearSpeed: 0.18,
    ForkliftObstacleInStopZone: false, ForkliftObstacleMinDistance: 3.20,
  });
  await page.locator('#enable').click();
  await sleep(400);
  const pad = await page.locator('#pad').boundingBox();
  await page.mouse.move(pad.x + pad.width / 2, pad.y + pad.height / 2);
  await page.mouse.down();
  await page.mouse.move(pad.x + pad.width * 0.775, pad.y + pad.height * 0.18, { steps: 12 });
  await sleep(1500);
  await say(page, 'driving');
  await shot(page, `hmi-page-03-connected-teleop-${DATE}.png`,
    'connected and driving: joystick held, ENABLE asserted, PLC lamps and metrics live');

  // 4. The safety group as this server leaves it — absent, greyed, not an error.
  await shot(page, `hmi-page-04-safety-mirrors-absent-${DATE}.png`,
    'Forklift/Safety/ absent on this server: the group greys rather than reading FALSE',
    { selector: 'main section:nth-of-type(4)' });

  await page.mouse.up();
  await sleep(600);

  // 5. The fork jog, held.
  const fork = page.locator('#forkup');
  const fbox = await fork.boundingBox();
  await page.mouse.move(fbox.x + fbox.width / 2, fbox.y + fbox.height / 2);
  await page.mouse.down();
  await sleep(1500);
  await say(page, 'fork jog held');
  await shot(page, `hmi-page-05-fork-jog-held-${DATE}.png`,
    'FORK UP held: HmiForkRequest 1.000 and the PLC answering with ForkliftForkSpeedRef');
  await page.mouse.up();
  await sleep(600);

  // 6. A latched process stop, formed by the PLC while the operator is driving.
  await page.mouse.move(pad.x + pad.width / 2, pad.y + pad.height / 2);
  await page.mouse.down();
  await page.mouse.move(pad.x + pad.width * 0.75, pad.y + pad.height * 0.22, { steps: 10 });
  await sleep(600);
  plant({
    ForkliftForkHeight: 1.20, ForkliftLinearSpeed: 0.0,
    ForkliftObstacleInStopZone: true, ForkliftObstacleMinDistance: 0.35,
  });
  await waitFor('the PLC to latch its process stop',
    async () => (await state(base)).metrics.ForkliftObstacleStopActive === true, 8000);
  await sleep(900);
  await say(page, 'process stop latched');
  await shot(page, `hmi-page-06-process-stop-latched-${DATE}.png`,
    'PLC-latched process stop over a live command: setpoints held at zero by the PLC');
  await page.mouse.up();
  await sleep(600);

  // 7. The page's own liveness window (§10.8 H6). Going offline is what a
  //    crashed or frozen browser looks like from inside the backend; coming back
  //    is what the operator sees afterwards.
  await context.setOffline(true);
  await sleep(2200);
  await context.setOffline(false);
  let staleCaught = false;
  try {
    await page.waitForFunction(
      () => (document.getElementById('beacon').textContent || '').indexOf('STALE') >= 0,
      null, { timeout: 3000, polling: 20 });
    await say(page, 'page beacon stale');
    await shot(page, `hmi-page-07-page-beacon-stale-${DATE}.png`,
      'the backend held the requests at rest while this page was silent (§10.8 H6)');
    staleCaught = true;
  } catch {
    log('the STALE beacon was not caught in the render race; the drop notice is next');
  }
  await sleep(700);
  await say(page, 'after the drop');
  await shot(page, `hmi-page-08-requests-dropped-notice-${DATE}.png`,
    'after the page returns: the drop is reported, nothing latched, no reset owed');

  // 8. Supervision lost: the PLC-side server goes away under a live session.
  stop('double');
  await waitFor('the link banner to leave CONNECTED',
    async () => (await page.locator('#linkstate').textContent()) !== 'CONNECTED', 20000);
  await sleep(1500);
  await say(page, 'link lost');
  await shot(page, `hmi-page-09-link-lost-${DATE}.png`,
    'supervision lost: the link banner leaves CONNECTED and the metrics grey out');

  await context.close();
  stop('plant');
  stop('hmi');
  await sleep(1200);
  return staleCaught;
}

// ------------------------------------------------- pass B: the safety mirror double
async function passSafetyMirrors(browser) {
  start('safetydouble', PYTHON, ['hmi/tools/safety_mirror_double.py',
    '--port', '4860', '--with-safety-mirrors']);
  await sleep(3000);
  start('hmi-safety', PYTHON, ['hmi/hmi_server.py',
    '--config', 'hmi/config-safety-mirror-double.yaml']);

  const base = 'http://127.0.0.1:8093';
  await waitFor('the HMI backend against the mirror double',
    async () => (await state(base)).session.state === 'CONNECTED');
  await waitFor('the mirrors to be present',
    async () => (await state(base)).safety.present === true);

  const context = await browser.newContext({ viewport: { width: 1680, height: 1450 } });
  const page = await context.newPage();
  page.on('console', (m) => log('  console:', m.type(), m.text()));
  await page.goto(base + '/', { waitUntil: 'load' });
  await sleep(1500);
  await say(page, 'safety mirrors present');
  await shot(page, `hmi-page-10-safety-mirrors-present-${DATE}.png`,
    'Forklift/Safety/ present: the four mirrors at their fail-safe start values',
    { selector: 'main section:nth-of-type(4)' });
  await shot(page, `hmi-page-11-safety-demand-banner-${DATE}.png`,
    'the F-CPU safety demand banner, visually distinct from the process-stop banner');

  await context.close();
  stop('hmi-safety');
  stop('safetydouble');
}

// --------------------------------------------------------------------- main
let browser;
try {
  browser = await chromium.launch({ args: ['--no-sandbox'] });
  log('chromium', browser.version());
  const staleCaught = await passLogicDouble(browser);
  await passSafetyMirrors(browser);
  log('page-beacon STALE captured:', staleCaught);
  log('--- screenshots ---');
  for (const s of shots) log(`${s.file}  ${s.bytes} bytes  ${s.caption}`);
} catch (err) {
  console.error('[capture] FAILED', err);
  process.exitCode = 1;
} finally {
  if (browser) { try { await browser.close(); } catch { /* closing anyway */ } }
  stopAll();
  await sleep(500);
}
