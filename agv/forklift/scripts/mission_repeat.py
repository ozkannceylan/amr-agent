#!/usr/bin/env python3
"""mission_repeat.py - drive the SAME autonomous mission N times and report
the rate, because one completion is an illustration and not a result.

WHY THIS EXISTS. `EVIDENCE_NAV2.md` section 8.6 records the cost of not
having it: "SUCCEEDED in 13.40 s" was carried for two gates as the result of
a route whose real distribution was 1 clean traverse, 2 completions after
69-94 s of recovery and 2 timeouts in five, and whose own first environment
had scored 1 success in 4 at identical parameters. Section 8.7 item 5 asks
for a repeat count in the harness. This is it.

WHAT IT DOES PER REPEAT, and every one of these is a lesson paid for once
already:

  * REFUSES TO START unless the machine is alone, by `pgrep` against the
    whole autonomy pattern, and prints the load, the `/dev/shm` count and a
    UTC stamp into the run's own log.
  * ISOLATES BOTH TRANSPORTS. `GZ_PARTITION` and `ROS_DOMAIN_ID` are set,
    distinct per repeat: `gz transport` does not use DDS and the ROS
    variable does not isolate the simulator (`docs/LESSONS.md` 2026-07-27).
  * GATES EACH BRING-UP STAGE ON A TOPIC CARRYING A MESSAGE, never on a
    sleep, and gives every repeat ITS OWN log, CSV and plan path stamped
    with the repeat index - a repeat that reuses its predecessor's names
    destroys the comparison it exists to make (`docs/LESSONS.md`
    2026-08-06). It REFUSES to overwrite an artefact that already exists.
  * SAMPLES THE MACHINE THROUGHOUT at 1 Hz - load, available memory, and
    the resident set of the autonomy processes - into a per-repeat CSV, so
    a stack that dies under load leaves a number behind rather than an
    impression. That is the second half of what m5-69 was sent to find out.
  * TEARS DOWN BY PATTERN against observed `ps` output, stops the `ros2`
    daemon so the next repeat cannot inherit its cache
    (`docs/LESSONS.md` 2026-08-05), and VERIFIES zero remaining processes
    before the next repeat starts.
  * CHECKS THE START POSE FIRST, through `start_pose_check.py`, and refuses
    a spawn the committed planner cannot plan from. m5-68 spent a session
    discovering that at the far end of a 100 s mission timeout.

WHAT IT DOES NOT DO. It does not tune anything, it does not retry a failed
repeat, and it does not decide what counts as success: the verdict of each
repeat is `nav2_run.py`'s own, and this file only counts them.

Usage:
  python3 agv/forklift/scripts/mission_repeat.py \\
      --spawn-x -3.0 --spawn-y -5.5 --x 1.0 --y -5.5 \\
      --repeats 5 --tag m5-69-dock --outdir agv/forklift/evidence
"""

import argparse
import datetime
import json
import math
import os
import shlex
import signal
import subprocess
import sys
import threading
import time

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..', '..'))

#: Every process the autonomy stack starts, as one pattern. The guard, the
#: sampler and the teardown all use THIS string, so a process that escapes
#: one of them cannot be counted by another.
PATTERN = ('gz[ ]sim|nav2|amcl|controller_server|bt_navigator|'
           'parameter_bridge|planner_server|velocity_smoother|'
           'robot_state_publisher|ekf_node|cmd_vel_to_tricycle|forklift_io|'
           'wheel_odometry|imu_gate|map_server|smoother_server|'
           'behavior_server|waypoint_follower|sensor_tf|sto_contactor|'
           'bt_navigator|collision_monitor|ros_gz_bridge|ros_gz_sim')

_SETUP = 'source /opt/ros/jazzy/setup.bash'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')


def sh(command, env=None, timeout=60, capture=True):
    """Run one bash -lc command with the ROS overlay sourced."""
    full = '{}; {}'.format(_SETUP, command)
    return subprocess.run(['bash', '-lc', full], env=env, timeout=timeout,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None,
                          text=True)


def matching_processes(env):
    out = sh("pgrep -af '{}' || true".format(PATTERN), env=env).stdout
    lines = [ln for ln in out.splitlines() if ln.strip()]
    # Exclude the sweep from itself: a pgrep whose own command line contains
    # the pattern counts itself (docs/LESSONS.md 2026-08-06).
    return [ln for ln in lines if 'pgrep' not in ln and 'bash -lc' not in ln]


# --------------------------------------------------------------------------- #
# the machine sampler
# --------------------------------------------------------------------------- #

class Sampler(threading.Thread):
    """1 Hz: load, available memory, process count, total RSS."""

    def __init__(self, path, env, period=1.0):
        threading.Thread.__init__(self, daemon=True)
        self.path = path
        self.env = env
        self.period = period
        # NOT `self._stop`: threading.Thread already owns that name, and
        # shadowing it makes Thread.join() call an Event and raise
        # "'Event' object is not callable" - the same shape of defect as the
        # rclpy `self._clock` shadowing in docs/LESSONS.md 2026-07-27,
        # arriving in the standard library instead.
        self._halt = threading.Event()
        self.peak_rss_mb = 0.0
        self.peak_load = 0.0
        self.min_avail_mb = float('inf')
        self.rows = 0

    def run(self):
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write('utc,load1,mem_available_mb,n_processes,'
                         'total_rss_mb\n')
            while not self._halt.is_set():
                try:
                    row = self._sample()
                except Exception as exc:                # pragma: no cover
                    row = None
                    handle.write('# sample failed: {}\n'.format(exc))
                if row:
                    handle.write(','.join(str(v) for v in row) + '\n')
                    handle.flush()
                    self.rows += 1
                    self.peak_load = max(self.peak_load, row[1])
                    self.peak_rss_mb = max(self.peak_rss_mb, row[4])
                    self.min_avail_mb = min(self.min_avail_mb, row[2])
                self._halt.wait(self.period)

    def _sample(self):
        with open('/proc/loadavg') as fh:
            load1 = float(fh.read().split()[0])
        avail = 0.0
        with open('/proc/meminfo') as fh:
            for line in fh:
                if line.startswith('MemAvailable:'):
                    avail = float(line.split()[1]) / 1024.0
                    break
        out = sh("ps -eo rss,args --no-headers | grep -E '{}' | "
                 "grep -v grep || true".format(PATTERN), env=self.env,
                 timeout=20).stdout
        rss = 0.0
        n = 0
        for line in out.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            rss += int(parts[0]) / 1024.0
            n += 1
        return [utc(), load1, round(avail, 1), n, round(rss, 1)]

    def stop(self):
        self._halt.set()
        self.join(timeout=5)


# --------------------------------------------------------------------------- #
# one repeat
# --------------------------------------------------------------------------- #

class Launched(object):
    def __init__(self, name, proc, log):
        self.name = name
        self.proc = proc
        self.log = log


def start_launch(name, command, env, log_path):
    handle = open(log_path, 'w', encoding='utf-8')
    handle.write('# {}\n# {}\n'.format(utc(), command))
    handle.flush()
    # `exec` so the launch REPLACES the shell and the process group this
    # driver signals at teardown is the launch itself. The command must
    # therefore be an executable, never a shell builtin: an earlier version
    # prefixed `cd <repo> &&` and `exec` answered `cd: not found`, which the
    # bring-up gate then reported as "/forklift/odom never advertised" three
    # minutes later. The working directory is set here instead.
    proc = subprocess.Popen(['bash', '-lc', '{}; exec {}'.format(
        _SETUP, command)], env=env, cwd=_REPO_ROOT, stdout=handle,
        stderr=subprocess.STDOUT, start_new_session=True)
    return Launched(name, proc, handle)


def wait_for_topic(topic, env, timeout, need_message=True):
    """Bounded FOREGROUND poll. Presence first, then one message: a topic
    can be advertised by a publisher that never publishes, and the failure
    mode this gate exists to catch looks exactly like that."""
    deadline = time.monotonic() + timeout
    seen = False
    while time.monotonic() < deadline:
        out = sh('ros2 topic list 2>/dev/null || true', env=env,
                 timeout=30).stdout
        if topic in out.split():
            seen = True
            break
        time.sleep(2.0)
    if not seen:
        return False, 'never advertised'
    if not need_message:
        return True, 'advertised'
    left = max(5.0, deadline - time.monotonic())
    res = sh('timeout {:.0f} ros2 topic echo --once {} > /dev/null'
             .format(left, topic), env=env, timeout=left + 20)
    if res.returncode != 0:
        return False, 'advertised but published nothing in {:.0f} s'.format(
            left)
    return True, 'advertised and publishing'


def wait_for_transform(parent, child, env, timeout):
    """AMCL IS DISTANCE-TRIGGERED, so a stationary vehicle publishes no pose
    and `/particle_cloud` carries no message however healthy the localizer is
    (`docs/LESSONS.md` 2026-08-06). The gate that means something is the
    TRANSFORM: `localization.launch.py` says so itself - "the check that this
    launch worked is that map -> forklift/odom appears on /tf, never a
    clean-looking log"."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        left = max(5.0, min(15.0, deadline - time.monotonic()))
        res = sh('timeout {:.0f} ros2 run tf2_ros tf2_echo {} {} 2>&1 | '
                 'head -20'.format(left, parent, child), env=env,
                 timeout=left + 20)
        if 'Translation' in (res.stdout or ''):
            return True, 'published'
        time.sleep(1.0)
    return False, 'never appeared on /tf'


def teardown(env, log):
    sh('ros2 daemon stop >/dev/null 2>&1 || true', env=env, timeout=60)
    for pattern in ("gz[ ]sim", "ros_gz|parameter_bridge",
                    "nav2|planner_server|controller_server|bt_navigator|"
                    "behavior_server|smoother_server|velocity_smoother|"
                    "waypoint_follower|map_server|amcl|collision_monitor",
                    "robot_state_publisher|ekf_node|cmd_vel_to_tricycle|"
                    "forklift_io|wheel_odometry|imu_gate|sensor_tf|"
                    "sto_contactor|nav2_run"):
        sh("pkill -f '{}' || true".format(pattern), env=env, timeout=60)
    time.sleep(4.0)
    left = matching_processes(env)
    if left:
        sh("pkill -9 -f '{}' || true".format(PATTERN), env=env, timeout=60)
        time.sleep(4.0)
        left = matching_processes(env)
    log('teardown: {} matching processes remain'.format(len(left)))
    for line in left:
        log('   LEFT: {}'.format(line))
    return len(left)


def run_once(args, index, base_env):
    tag = '{}-r{}'.format(args.tag, index)
    out = args.outdir
    paths = {
        'log': os.path.join(out, tag + '-run.txt'),
        'csv': os.path.join(out, tag + '-run.csv'),
        'plan': os.path.join(out, tag + '-plan.json'),
        'machine': os.path.join(out, tag + '-machine.csv'),
        'sim': os.path.join(out, tag + '-sim.log'),
        'loc': os.path.join(out, tag + '-localization.log'),
        'nav': os.path.join(out, tag + '-navigation.log'),
    }
    for key, path in paths.items():
        if os.path.exists(path):
            raise SystemExit(
                'REFUSING: {} already exists. An evidence filename carries '
                'the run that produced it; pick a new --tag rather than '
                'overwriting the run this one would be compared against.'
                .format(path))

    log_handle = open(paths['log'], 'w', encoding='utf-8')

    def log(text):
        line = '[{}] {}'.format(utc(), text)
        print(line, flush=True)
        log_handle.write(line + '\n')
        log_handle.flush()

    env = dict(base_env)
    env['GZ_PARTITION'] = '{}r{}'.format(args.partition, index)
    env['ROS_DOMAIN_ID'] = str(args.domain + index)
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)

    record = {
        'tag': tag, 'index': index, 'started_utc': utc(),
        'gz_partition': env['GZ_PARTITION'],
        'ros_domain_id': env['ROS_DOMAIN_ID'],
        'spawn_world': [args.spawn_x, args.spawn_y, args.spawn_yaw],
        'goal_world': [args.x, args.y, args.yaw],
        'mode': args.mode,
    }

    log('=== repeat {} of {}  tag {}'.format(index, args.repeats, tag))
    log('isolation GZ_PARTITION={} ROS_DOMAIN_ID={}'.format(
        env['GZ_PARTITION'], env['ROS_DOMAIN_ID']))

    # -- the guard -------------------------------------------------------- #
    left = matching_processes(env)
    with open('/proc/loadavg') as fh:
        loadavg = fh.read().strip()
    shm = len(os.listdir('/dev/shm'))
    log('guard: {} matching processes, load [{}], /dev/shm {} entries'
        .format(len(left), loadavg, shm))
    record['guard'] = {'processes': len(left), 'loadavg': loadavg, 'shm': shm}
    if left:
        for line in left:
            log('   BLOCKING: {}'.format(line))
        log('REFUSING to start: the machine is not alone.')
        record['verdict'] = 'REFUSED_MACHINE_NOT_ALONE'
        log_handle.close()
        return record

    sampler = Sampler(paths['machine'], env)
    sampler.start()
    launched = []
    try:
        # -- stage 1: the simulator and the vehicle ----------------------- #
        cmd = ('ros2 launch sim/launch/warehouse_bringup.launch.py '
               'x:={x} y:={y} yaw:={yaw} estimator:=true'
               .format(x=args.spawn_x, y=args.spawn_y, yaw=args.spawn_yaw))
        log('stage 1 (simulator + vehicle): {}'.format(cmd))
        launched.append(start_launch('sim', cmd, env, paths['sim']))
        ok, why = wait_for_topic('/forklift/odom', env, args.stage_timeout)
        log('   /forklift/odom: {}'.format(why))
        if not ok:
            record['verdict'] = 'BRINGUP_FAILED_SIM'
            return record

        # -- stage 2: the localizer --------------------------------------- #
        mapx, mapy, mapyaw = world_to_map(args.spawn_x, args.spawn_y,
                                          args.spawn_yaw)
        log('spawn world ({:+.4f}, {:+.4f}, {:+.4f}) -> map ({:+.6f}, '
            '{:+.6f}, {:+.6f})'.format(args.spawn_x, args.spawn_y,
                                       args.spawn_yaw, mapx, mapy, mapyaw))
        record['spawn_map'] = [mapx, mapy, mapyaw]
        cmd = ('ros2 launch agv/forklift/launch/localization.launch.py '
               'initial_pose_x:={x:.6f} initial_pose_y:={y:.6f} '
               'initial_pose_yaw:={yaw:.6f}'
               .format(x=mapx, y=mapy, yaw=mapyaw))
        log('stage 2 (localizer): {}'.format(cmd))
        launched.append(start_launch('loc', cmd, env, paths['loc']))
        ok, why = wait_for_topic('/particle_cloud', env, args.stage_timeout,
                                 need_message=False)
        log('   /particle_cloud: {}'.format(why))
        if ok:
            ok, why = wait_for_transform('map', 'forklift/odom', env,
                                         args.stage_timeout)
            log('   map -> forklift/odom: {}'.format(why))
        if not ok:
            record['verdict'] = 'BRINGUP_FAILED_LOCALIZATION'
            return record

        # -- stage 3: navigation ------------------------------------------ #
        cmd = ('ros2 launch agv/forklift/launch/navigation.launch.py '
               'gate:={gate} cmd_topic:={topic}'
               .format(gate=args.gate, topic=args.cmd_topic))
        log('stage 3 (navigation): {}'.format(cmd))
        launched.append(start_launch('nav', cmd, env, paths['nav']))
        ok, why = wait_for_topic('/plan', env, args.stage_timeout,
                                 need_message=False)
        log('   /plan: {}'.format(why))
        if not ok:
            record['verdict'] = 'BRINGUP_FAILED_NAVIGATION'
            return record
        log('settling {:.0f} wall s before the goal'.format(args.pre_goal))
        time.sleep(args.pre_goal)

        # -- the mission --------------------------------------------------- #
        if args.mode == 'goal':
            mission = ('cd {root} && python3 agv/forklift/scripts/nav2_run.py '
                       'goal --x {x} --y {y} --yaw {yaw} --settle {settle} '
                       '--timeout {timeout} --csv {csv} --plan {plan} '
                       '--cmd-topic {topic}'
                       .format(root=shlex.quote(_REPO_ROOT), x=args.x,
                               y=args.y, yaw=args.yaw, settle=args.settle,
                               timeout=args.timeout,
                               csv=shlex.quote(paths['csv']),
                               plan=shlex.quote(paths['plan']),
                               topic=args.cmd_topic))
        else:
            mission = ('cd {root} && python3 agv/forklift/scripts/nav2_run.py '
                       'stage --x {x} --y {y} --yaw {yaw} --d {d} '
                       '--max-go-arounds {ga} --settle {settle} --csv {csv} '
                       '--plan {plan} --cmd-topic {topic}'
                       .format(root=shlex.quote(_REPO_ROOT), x=args.x,
                               y=args.y, yaw=args.yaw, d=args.d,
                               ga=args.max_go_arounds, settle=args.settle,
                               csv=shlex.quote(paths['csv']),
                               plan=shlex.quote(paths['plan']),
                               topic=args.cmd_topic))
        log('mission: {}'.format(mission))
        t0 = time.monotonic()
        try:
            res = sh(mission, env=env, timeout=args.wall_timeout)
            output = res.stdout
            rc = res.returncode
        except subprocess.TimeoutExpired:
            output = '(no output: the mission exceeded --wall-timeout)'
            rc = 124
        record['mission_wall_s'] = round(time.monotonic() - t0, 2)
        record['mission_returncode'] = rc
        log_handle.write(output + '\n')
        log_handle.flush()
        print(output, flush=True)

        # -- did the stack survive its own mission? ------------------------ #
        alive = {}
        for item in launched:
            alive[item.name] = item.proc.poll() is None
        record['launch_alive_after_mission'] = alive
        log('launch processes alive after the mission: {}'.format(alive))
        server = sh("ros2 action list 2>/dev/null | grep -c navigate_to_pose "
                    "|| true", env=env, timeout=60).stdout.strip()
        record['navigate_to_pose_present_after'] = server
        log('/navigate_to_pose present after the mission: {}'.format(server))

        if os.path.exists(paths['plan']):
            with open(paths['plan'], encoding='utf-8') as fh:
                record['plan'] = json.load(fh)
        record['verdict'] = _verdict(record)
        log('VERDICT {}'.format(record['verdict']))
        return record
    finally:
        sampler.stop()
        record['machine'] = {
            'samples': sampler.rows,
            'peak_load1': sampler.peak_load,
            'peak_stack_rss_mb': sampler.peak_rss_mb,
            'min_mem_available_mb': (None if sampler.min_avail_mb == float(
                'inf') else sampler.min_avail_mb),
        }
        log('machine over the repeat: peak load {:.2f}, peak stack RSS '
            '{:.0f} MB, min available memory {} MB, {} samples'.format(
                sampler.peak_load, sampler.peak_rss_mb,
                record['machine']['min_mem_available_mb'], sampler.rows))
        for item in launched:
            if item.proc.poll() is None:
                try:
                    os.killpg(os.getpgid(item.proc.pid), signal.SIGINT)
                except Exception:
                    pass
        time.sleep(3.0)
        record['processes_left_after_teardown'] = teardown(env, log)
        record['ended_utc'] = utc()
        log_handle.close()


def _verdict(record):
    plan = record.get('plan') or {}
    status = plan.get('status') or plan.get('verdict')
    if status is None:
        return 'NO_RESULT'
    return str(status)


def world_to_map(x, y, yaw):
    map_dir = os.path.join(_REPO_ROOT, 'sim', 'maps', 'warehouse')
    if map_dir not in sys.path:
        sys.path.insert(0, map_dir)
    import register_map
    rec = register_map.load_registration(register_map.DEFAULT_REGISTRATION)
    th = rec['theta_rad']
    c, s = math.cos(th), math.sin(th)
    return (c * x - s * y + rec['t_x_m'], s * x + c * y + rec['t_y_m'],
            yaw + th)


def check_pose(label, x, y, yaw):
    """Refuse a start or a goal the committed planner cannot use."""
    res = subprocess.run(
        [sys.executable, os.path.join(_THIS_DIR, 'start_pose_check.py'),
         'pose', '--x', str(x), '--y', str(y), '--yaw', str(yaw)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print('--- {} pose check ---'.format(label))
    print(res.stdout)
    return res.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--spawn-x', type=float, required=True)
    parser.add_argument('--spawn-y', type=float, required=True)
    parser.add_argument('--spawn-yaw', type=float, default=0.0)
    parser.add_argument('--x', type=float, required=True,
                        help='goal x in the WORLD frame [m]')
    parser.add_argument('--y', type=float, required=True)
    parser.add_argument('--yaw', type=float, default=0.0)
    parser.add_argument('--mode', choices=('goal', 'stage'), default='goal')
    parser.add_argument('--d', type=float, default=4.5,
                        help='staging distance, --mode stage only')
    parser.add_argument('--max-go-arounds', type=int, default=2)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--outdir', default=os.path.join(
        _REPO_ROOT, 'agv', 'forklift', 'evidence'))
    parser.add_argument('--partition', default=None,
                        help='GZ_PARTITION prefix; defaults to --tag')
    parser.add_argument('--domain', type=int, default=60,
                        help='ROS_DOMAIN_ID base; repeat i uses base + i')
    parser.add_argument('--gate', default='false',
                        help='navigation.launch.py gate: argument')
    parser.add_argument('--cmd-topic', default='/cmd_vel_smoothed')
    parser.add_argument('--settle', type=float, default=30.0)
    parser.add_argument('--pre-goal', type=float, default=25.0,
                        help='WALL seconds after /plan appears before the '
                             'goal is sent (EVIDENCE_NAV2 12.2)')
    parser.add_argument('--timeout', type=float, default=120.0,
                        help='SIMULATION seconds for the mission')
    parser.add_argument('--stage-timeout', type=float, default=180.0,
                        help='wall seconds for each bring-up stage')
    parser.add_argument('--wall-timeout', type=float, default=900.0)
    parser.add_argument('--between', type=float, default=10.0,
                        help='wall seconds of quiet between repeats')
    parser.add_argument('--skip-pose-check', action='store_true')
    args = parser.parse_args(argv)
    if args.partition is None:
        args.partition = args.tag.replace('-', '')

    os.makedirs(args.outdir, exist_ok=True)
    if not args.skip_pose_check:
        ok_start = check_pose('START', args.spawn_x, args.spawn_y,
                              args.spawn_yaw)
        ok_goal = check_pose('GOAL', args.x, args.y, args.yaw)
        if not (ok_start and ok_goal):
            raise SystemExit(
                'REFUSING: the committed planner cannot use one of these '
                'poses under allow_unknown false. Fix the geometry, not the '
                'planner. (--skip-pose-check runs it anyway, which is only '
                'sensible when the refusal is the measurement.)')

    base_env = dict(os.environ)
    results = []
    summary_path = os.path.join(args.outdir, args.tag + '-summary.json')
    for index in range(1, args.repeats + 1):
        record = run_once(args, index, base_env)
        results.append(record)
        # Written after EVERY repeat, not at the end: a session that dies
        # mid-sweep must still leave the repeats it finished behind
        # (docs/LESSONS.md 2026-08-04).
        with open(summary_path, 'w', encoding='utf-8') as fh:
            json.dump({'tag': args.tag, 'repeats_requested': args.repeats,
                       'runs': results}, fh, indent=2)
        if index < args.repeats:
            time.sleep(args.between)

    print('\n=== {} : {} repeats ==='.format(args.tag, len(results)))
    counts = {}
    for record in results:
        counts[record.get('verdict', 'NO_RESULT')] = counts.get(
            record.get('verdict', 'NO_RESULT'), 0) + 1
    for verdict, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print('  {:28s} {} of {}'.format(verdict, n, len(results)))
    print('summary written to {}'.format(summary_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
