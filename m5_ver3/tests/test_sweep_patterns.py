"""Every process this stack starts is a process `stop` can find - and the
list of processes is PARSED OUT OF THE SCRIPT rather than typed here.

WHAT THIS LOCKS. `m5v3.sh`'s `spawn` records the pid of the `ros2 run`
WRAPPER, and that wrapper FORKS the real executable: two processes per
node, and the pidfile knows about one of them. `stop`'s second pass - the
SWEEP over `tools/_common.sh`'s `M5V3_PATTERNS`, filtered by `ours()` - is
what catches the other. A child whose command line no pattern nominates is
therefore ORPHANED by a `stop` that prints "down." and exits zero.

MEASURED, 2026-08-27, when F3 Task 3 added `localization_slam_toolbox_node`
to `start()` and not to that list. NINE of them accumulated across nine
bringups, every one still publishing `map` -> `odom` on domain 97 out of a
world that no longer existed. What it looked like from the outside was two
completely different faults: an EKF that "never came up" - its topic lost
in a graph carrying nine stale participants - and a localiser answering
0.659 m from its seed, BIT-IDENTICALLY, on three consecutive bringups,
which reads exactly like the snap-relocalisation pathology
docs/reports/m5v3-04 predicts for that arm. Neither was real.

---- WHY THE LIST IS PARSED AND NOT WRITTEN DOWN ----

The first cut of this file carried a hand-maintained table of the children
`m5v3.sh` spawns, and that table has the defect it was written to catch:
**a child added to `start()` and not to the table passes.** It is
`tools/_common.sh`'s own prose obligation - "a process added to m5v3.sh's
start() is added HERE" - one layer up and no more binding, and F4 adds
more children than any phase on this track.

So `spawned()` below reads `m5v3.sh` itself, finds every `spawn <name>
<cmd...>` invocation including its line continuations, and expands the
shell variables on it from that script's own assignments and from
`config.yaml`. **The coverage claim is then literally true**: what the
test iterates IS what the script starts.

A VARIABLE WITH TWO ASSIGNMENTS EXPANDS TO BOTH, and both must be
nominated. `LOC_PACKAGE` is `nav2_amcl` on one arm and `slam_toolbox` on
the other, and a pattern set that covered one arm and not the other is
exactly the hole this file exists for.

WHAT IS DELIBERATELY NOT PARSED: `tools/build_map.sh`. Its children run on
`isolation.map_ros_domain_id` with no `GZ_PARTITION` at all, so they are
not this stack's to kill and `ours()` spares them by construction - see
the mapper test at the bottom, which asserts the sweep does NOT nominate
them.

---- AND ONE MORE CLAIM ABOUT THE SAME SCRIPT ----

Since this file already parses `m5v3.sh`, it also asks the question the
phase-end wave got wrong: **is an arm-specific check inside its arm's
guard?** `check_slam_mode()` landed as an UNCONDITIONAL call, and
`amcl.yaml` has no `mode:` line at all - so every `--localize amcl`
bringup, the shipping default, refused with "no mode: line at all" and
started nothing. `bash -n` was clean, the suite was green, and the slam
arm the change was demonstrated on passed both directions. Only the arm
that was not re-run was broken.

`conditions_at()` below tracks `if`/`elif`/`else`/`fi` nesting over the
folded script and reports the conditions in scope at any line, and
`test_every_arm_named_check_is_called_inside_its_arm_guard` requires that
a function whose NAME carries an arm label is reached only under a
condition naming that arm.

NO ROS, NO GAZEBO AND NO RUNNING STACK: this reads three files off disk.
"""
import itertools
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

_M5V3 = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# ----------------------------------------------------------------------
# the parser
# ----------------------------------------------------------------------

def join_continuations(text):
    """A shell script with its backslash-newlines folded away.

    `spawn` calls on this track run to a dozen lines; a parser that read
    line by line would see the first word of each and nothing else.
    """
    folded = re.sub(r"\\\n\s*", " ", text)
    # AND THE RUNS OF SPACES THE FOLD LEAVES GO WITH IT. `pgrep -f` reads
    # a process's argv joined by single spaces, so that is the string a
    # pattern is really tested against.
    return "\n".join(re.sub(r"[ \t]{2,}", " ", line)
                     for line in folded.splitlines())


def assignments(text):
    """`NAME="value"` at the start of a line, as name -> [values].

    A LIST AND NOT A VALUE, because a script may assign the same name in
    more than one place. Only double-quoted right-hand sides are read:
    everything this script resolves a spawn through is written that way,
    and a parser that guessed at the rest would report a coverage it had
    not checked.
    """
    found = {}
    for name, value in re.findall(
            r'(?m)^\s*(?:local\s+)?([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"', text):
        # A COMMAND SUBSTITUTION IS NOT A VALUE AND IS NOT GUESSED AT.
        # `REPO="$(cd "$M5V3/.." && pwd)"` would be read by the regex
        # above as the five characters `$(cd `, and a parser that
        # substituted THAT would build a command line nobody runs and
        # then test a pattern against it.
        if "$(" in value or "`" in value:
            continue
        found.setdefault(name, [])
        if value not in found[name]:
            found[name].append(value)
    return found


#: The three names this track resolves at RUNTIME and no file can state:
#: the repository root and this directory (both `$(cd … && pwd)`) and the
#: user's home. They are seeded with placeholders because they appear only
#: in PATH positions - a value here can never be the name of a program,
#: which is what test_no_unresolved_variable_could_have_named_a_program
#: checks rather than assumes.
RUNTIME_ROOTS = {"REPO": ["/repo"], "M5V3": ["/repo/m5_ver3"],
                 "HOME": ["/home/rig"]}


#: A `case … esac`, INCLUDING THE ONE-LINE KIND. `ours()` and
#: `status()` both write the whole construct on one line, and a
#: pattern that demanded `esac` at the START OF A LINE would swallow
#: everything from there to the next block `esac` - which on this
#: script is hundreds of lines, including the assignments three
#: spawns resolve through. The symptom was a command line that "did
#: not resolve" for a reason four hundred lines away from it.
#: Non-greedy to the first `esac` TOKEN is what both spellings have
#: in common.
CASE_BLOCK = re.compile(r"(?ms)^[ \t]*case\b.*?\besac\b")


def case_scopes(text):
    """One environment fragment per `case` branch.

    WHY THE BRANCHES ARE SCOPES AND NOT ALTERNATIVES. `configure()`
    assigns LOC_PACKAGE, LOC_EXECUTABLE and LOC_NODE once per arm inside
    one `case`, and those three are CORRELATED: `slam_toolbox` goes with
    `localization_slam_toolbox_node` and never with `amcl`. A parser that
    treated each variable as independently two-valued would generate
    `ros2 run nav2_amcl localization_slam_toolbox_node` - a command
    nobody runs - and then demand a pattern for it, which is a test
    asking to be satisfied with a lie.
    """
    out = []
    for block in CASE_BLOCK.findall(text):
        for branch in block.split(";;"):
            local = assignments(branch)
            if local:
                out.append(local)
    return out


def strip_case_blocks(text):
    return CASE_BLOCK.sub("", text)


def expand(word, env, depth=200):
    """Every value `word` can take, substituting $NAME and ${NAME…}.

    Returns a list because a name may have several assignments outside a
    `case`. An unknown BARE `$NAME` is left as written - it cannot be
    resolved and pretending otherwise would hide it from the caller. An
    unknown BRACED `${NAME…}` becomes empty, which is what bash does with
    the two forms this script uses it for (`${x[@]+…}` on an unset array,
    and a pattern substitution on a name that is not there).
    """
    # A COMMAND SUBSTITUTION IS AN ARGUMENT AND NEVER A PROGRAM NAME.
    # `-p map_start_pose:=[$(… map_register.py seed …)]` puts a POSE on
    # that command line; what it cannot put there is the name of the
    # thing being run, so it is removed rather than resolved.
    word = re.sub(r"\$\((?:[^()]|\([^()]*\))*\)", "", word)
    out = [word]
    for _ in range(depth):
        grown = []
        for candidate in out:
            # THE FIRST *RESOLVABLE* OCCURRENCE AND NOT THE FIRST
            # OCCURRENCE. An unknown bare name early in a long command
            # line would otherwise block every name after it, and the
            # caller would be told the command did not resolve when what
            # failed was one token of it.
            chosen = None
            for match in re.finditer(
                    r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)[^{}]*(?:\{[^{}]*\})?"
                    r"[^{}]*\}|([A-Za-z_][A-Za-z0-9_]*))", candidate):
                if (match.group(1) or match.group(2)) in env \
                        or match.group(1) is not None:
                    chosen = match
                    break
            if chosen is None:
                grown.append(candidate)
                continue
            name = chosen.group(1) or chosen.group(2)
            head, tail = candidate[:chosen.start()], candidate[chosen.end():]
            if name in env:
                for value in env[name]:
                    grown.append(head + value + tail)
            else:
                grown.append(head + tail)
        if grown == out:
            break
        out = list(dict.fromkeys(grown))[:64]
    # THE SHELL'S QUOTES ARE NOT ON THE COMMAND LINE. `pgrep -f` matches
    # argv, and argv has been through the shell - `ros2 run "$PKG" amcl`
    # reaches /proc as `ros2 run nav2_amcl amcl`.
    return [c.replace('"', "").replace("'", "") for c in out]


def spawn_calls(text):
    """Every `spawn <name> <cmd…>` in a script, as (name, command), still
    carrying its variables."""
    out = []
    for line in join_continuations(text).splitlines():
        stripped = line.strip()
        if not stripped.startswith("spawn ") or stripped.startswith("spawn()"):
            continue
        parts = stripped[len("spawn "):].strip().split(None, 1)
        if len(parts) == 2:
            out.append((parts[0], parts[1]))
    return out


def spawned(text, base_env, scopes=()):
    """Every spawn, expanded to the command lines that FULLY resolve.

    Each spawn is expanded under the base environment and under the base
    plus each `case` branch, and only the candidates with no `$` left in
    them are returned - a half-resolved string is not a command line and
    a pattern tested against one would be a coverage claim nobody made.
    """
    out = []
    envs = [base_env]
    for scope in scopes:
        env = dict(base_env)
        env.update(scope)
        envs.append(env)
    for name, command in spawn_calls(text):
        resolved, partial = [], []
        for env in envs:
            for candidate in expand(command, env):
                bucket = resolved if "$" not in candidate else partial
                bucket.append(candidate)
        # THE LABEL CARRIES EVERY NAME THE SPAWN CAN TAKE, joined, because
        # one of them would be the wrong one in a failure message: the
        # localiser spawn is `amcl` under one scope and `slam_loc` under
        # the other, and a message naming the arm that is fine while
        # printing the command line of the arm that is not is a message
        # that sends an operator to the wrong file.
        labels = [c for env in envs for c in expand(name, env)
                  if "$" not in c]
        out.append(("|".join(dict.fromkeys(labels)) or name,
                    list(dict.fromkeys(resolved)),
                    list(dict.fromkeys(partial))))
    return out


#: `if`, `elif`, `else` and `fi` as they open and close a block. Bash
#: writes them as words, so a word boundary is the whole of the parse -
#: and comments are removed first, because this script's prose says `if`
#: more often than its code does.
BLOCK_WORD = re.compile(r"(?<![\w-])(if|elif|else|fi)(?![\w-])")
COMMENT_LINE = re.compile(r"(?m)^[ \t]*#.*$")


def conditions_at(text):
    """Every line of `text`, with the `if` conditions in scope at it.

    Yields (line number, line, [condition, ...]) with the conditions
    outermost first. `elif` and `else` REPLACE the condition they follow
    rather than nesting under it, which is what they do.

    IT IS A NESTING COUNT AND NOT A SHELL. What it is asked is whether a
    call sits under a guard that mentions a name, and for that a stack of
    the conditions between `if` and `fi` is exactly enough. A construct
    it cannot see - a guard written as a `case`, or one inside a function
    called from elsewhere - shows up as a MISSING condition, which fails
    the test rather than passing it silently.
    """
    stack = []
    for number, raw in enumerate(
            COMMENT_LINE.sub("", join_continuations(text)).splitlines(), 1):
        before = list(stack)
        deepest = None
        condition = raw.split("; then", 1)[0].strip()
        for word in BLOCK_WORD.findall(raw):
            if word == "if":
                stack.append(condition[len("if "):].strip()
                             if condition.startswith("if ") else condition)
                deepest = list(stack)
            elif word in ("elif", "else"):
                if stack:
                    stack[-1] = condition
                deepest = list(stack)
            elif stack:
                stack.pop()
        # A LINE IS JUDGED BY THE DEEPEST SCOPE IT REACHES, which is
        # the only reading that survives a one-liner: `if X; then
        # check; fi` opens and closes on one line, and the guard is
        # real for exactly the statement between them.
        #   A COPY EVERY TIME, because `stack` is mutated on every
        #   line after this one and a caller that kept the reference
        #   would be handed the scope at end of file, not this one.
        if deepest is not None:
            yield number, raw, deepest
        elif len(stack) < len(before):
            yield number, raw, before
        else:
            yield number, raw, list(stack)


def config_env():
    """config.yaml as CFG_<DOTTED_UPPER> -> [value], which is the shape
    `tools/_common.sh`'s config_env() eval's into the script."""
    with open(os.path.join(_M5V3, "config.yaml"), encoding="utf-8") as handle:
        tree = yaml.safe_load(handle)
    found = {}

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, path + [str(key)])
        elif not isinstance(node, list):
            found["CFG_" + "_".join(path).upper()] = [str(node)]

    walk(tree, [])
    return found


def read(*parts):
    with open(os.path.join(_M5V3, *parts), encoding="utf-8") as handle:
        return handle.read()


def patterns():
    """The M5V3_PATTERNS array, as the shell spells it."""
    match = re.search(r"^M5V3_PATTERNS=\((.*?)\)\s*$",
                      read("tools", "_common.sh"), re.DOTALL | re.MULTILINE)
    assert match, "tools/_common.sh no longer defines M5V3_PATTERNS"
    return re.findall(r'"([^"]+)"', match.group(1))


def stack():
    """(base environment, case scopes) for m5v3.sh and what it sources."""
    script, common = read("m5v3.sh"), read("tools", "_common.sh")
    base = config_env()
    base.update(RUNTIME_ROOTS)
    for name, values in itertools.chain(
            assignments(strip_case_blocks(script)).items(),
            assignments(strip_case_blocks(common)).items()):
        base.setdefault(name, [])
        for value in values:
            if value not in base[name]:
                base[name].append(value)
    return base, case_scopes(script) + case_scopes(common)


def stack_spawns():
    base, scopes = stack()
    return spawned(read("m5v3.sh"), base, scopes)


# ----------------------------------------------------------------------
# the parser, tested before it is trusted
# ----------------------------------------------------------------------

def one(text, env=None, scopes=()):
    got = spawned(text, dict(env or {}), scopes)
    assert len(got) == 1, got
    return got[0]


def test_a_continuation_is_folded_into_one_command():
    text = ('spawn ekf ros2 run robot_localization ekf_node'
            ' \\\n    --ros-args\n')
    assert one(text) == ("ekf",
                         ["ros2 run robot_localization ekf_node --ros-args"],
                         [])


def test_a_config_variable_on_the_command_is_expanded():
    name, resolved, _ = one('spawn amcl ros2 run "$CFG_A_B" amcl\n',
                            {"CFG_A_B": ["nav2_amcl"]})
    assert (name, resolved) == ("amcl", ["ros2 run nav2_amcl amcl"])


def test_a_braced_variable_is_expanded_too():
    assert expand("${X}/lib", {"X": ["/opt"]}) == ["/opt/lib"]


def test_a_bash_pattern_substitution_keeps_the_NAME_it_is_applied_to():
    # `${CFG_RF2O_WORKSPACE/#~/$HOME}` is how m5v3.sh expands a leading
    # tilde. What matters here is the workspace, not the rewrite.
    assert expand("${X/#~/$HOME}/bin", {"X": ["~/ws"]}) == ["~/ws/bin"]


def test_an_unset_braced_expansion_disappears_the_way_bash_drops_it():
    assert expand("a${NOPE[@]+b}c", {}) == ["ac"]


def test_an_unknown_BARE_variable_is_left_visible_and_never_guessed():
    assert expand("$NOPE/x", {}) == ["$NOPE/x"]


def test_an_unknown_variable_does_not_block_the_ones_after_it():
    # THE BUG THIS FILE FOUND IN ITSELF. Substituting the first
    # OCCURRENCE rather than the first RESOLVABLE one left every name
    # after an unknown one unresolved, and reported the command as
    # unparseable for a reason nowhere near the token that caused it.
    assert expand("$NOPE $A", {"A": ["ok"]}) == ["$NOPE ok"]


def test_a_command_substitution_is_removed_and_not_resolved():
    # `-p map_start_pose:=[$(… seed)]` puts a POSE on the command line.
    # What a command substitution cannot put there is the name of the
    # program being run.
    assert expand("run x [$(echo $seed | tr ' ' ',')]", {}) == ["run x []"]


def test_a_local_declaration_is_an_assignment():
    assert assignments('    local base="$CFG_F"\n') == {"base": ["$CFG_F"]}


def test_a_command_substitution_is_never_read_AS_an_assignment():
    assert assignments('REPO="$(cd "$M5V3/.." && pwd)"\n') == {}


def test_an_indirect_variable_resolves_through_another():
    env = assignments('BIN="$PREFIX/lib/x"\nPREFIX="$HOME/f"\nHOME="/h"\n')
    assert expand("$BIN", env) == ["/h/f/lib/x"]


def test_a_variable_with_TWO_assignments_expands_to_BOTH():
    env = assignments('    A="one"\n    A="two"\n')
    assert env["A"] == ["one", "two"]
    assert sorted(expand("$A", env)) == ["one", "two"]


def test_a_case_branch_is_a_SCOPE_and_its_variables_stay_correlated():
    # THE PROPERTY THE WHOLE FILE TURNS ON. configure() assigns
    # LOC_PACKAGE and LOC_EXECUTABLE once per arm; treating them as two
    # independently two-valued names would generate
    # `ros2 run nav2_amcl localization_slam_toolbox_node` - a command
    # nobody runs - and then demand a pattern for it.
    script = ('case "$X" in\n'
              '    a)\n        P="pkg_a"\n        E="exe_a" ;;\n'
              '    b)\n        P="pkg_b"\n        E="exe_b" ;;\n'
              'esac\n'
              'spawn n ros2 run "$P" "$E"\n')
    scopes = case_scopes(script)
    assert len(scopes) == 2
    _, resolved, _ = one(script, assignments(strip_case_blocks(script)),
                         scopes)
    assert sorted(resolved) == ["ros2 run pkg_a exe_a",
                                "ros2 run pkg_b exe_b"]


def test_a_ONE_LINE_case_does_not_swallow_the_rest_of_the_script():
    # ours() and status() both write `case "$pid" in ''|*[!0-9]*)
    # continue ;; esac` on one line. A block pattern that wanted `esac`
    # at the start of a line would eat everything to the NEXT block esac.
    script = ('case "$p" in \'\'|*) continue ;; esac\n'
              'KEEP="found"\n')
    assert assignments(strip_case_blocks(script)) == {"KEEP": ["found"]}


def test_the_spawn_FUNCTION_DEFINITION_is_not_read_as_a_spawn():
    assert spawned('spawn() {  # spawn <name> <cmd...>\n', {}) == []


def test_a_spawn_with_no_command_is_skipped_rather_than_half_read():
    assert spawned("spawn lonely\n", {}) == []


def test_the_name_is_expanded_as_well_as_the_command():
    name, _, _ = one('spawn "$CFG_N" ros2 run nav2_amcl amcl\n',
                     {"CFG_N": ["amcl"]})
    assert name == "amcl"


def test_a_spawn_whose_NAME_differs_per_scope_reports_both():
    script = ('case "$X" in\n'
              '    a)\n        N="amcl" ;;\n'
              '    b)\n        N="slam_loc" ;;\n'
              'esac\n'
              'spawn "$N" ros2 run p e\n')
    name, _, _ = one(script, assignments(strip_case_blocks(script)),
                     case_scopes(script))
    assert name == "amcl|slam_loc"


def test_a_half_resolved_command_is_reported_as_PARTIAL_and_never_checked():
    _, resolved, partial = one('spawn n ros2 run "$NOPE" x\n', {})
    assert resolved == [] and partial == ["ros2 run $NOPE x"]


# ----------------------------------------------------------------------
# and now the claim itself, over the real script
# ----------------------------------------------------------------------

def test_the_parse_finds_the_children_this_stack_actually_starts():
    # A PARSER THAT FOUND NOTHING WOULD PASS EVERY TEST BELOW. This is the
    # floor under the coverage claim: the six children of the default
    # stack, the gated gui, and all four optional arms.
    names = set()
    for label, _, _ in stack_spawns():
        names.update(label.split("|"))
    for child in ("world", "bridge", "imgbridge", "odom", "imutf", "ekf",
                  "gui", "lasertf", "rf2o", "rf2ocov", "fuse",
                  "map_server", "amcl", "slam_loc",
                  # F4 Task 1's two, and they are NOT arm-gated: the
                  # command path is one line and a line that exists on
                  # some arms is not one.
                  "smoother", "navcmd"):
        assert child in names, "the parse lost the `{}` child".format(child)


def test_every_spawn_resolves_to_at_least_one_real_command_line():
    # A spawn whose variables this parser cannot resolve is a spawn it
    # cannot check, and silently skipping it is how a hand-maintained
    # list fails. Failing here is the parser asking to be taught.
    for name, resolved, partial in stack_spawns():
        assert resolved, (
            "`spawn {}` never fully resolved; the closest this parser got "
            "was `{}`".format(name, (partial or ["(nothing)"])[0]))


def test_every_spawned_child_is_nominated_by_a_pattern():
    # EITHER NAME WILL DO AND THAT IS THE POINT. `ros2 run` forks, so the
    # wrapper's command line reads `ros2 run <package> <executable>` and
    # the node's own reads <prefix>/lib/<package>/<executable>: a pattern
    # matching either string is on BOTH command lines. What may not
    # happen is neither.
    known = patterns()
    for name, resolved, _ in stack_spawns():
        for command in resolved:
            assert any(p in command for p in known), (
                "`spawn {}` runs `{}` and no pattern in tools/_common.sh "
                "nominates it. `stop` would kill the wrapper out of the "
                'pidfile, leave the node itself running, and print '
                '"down."'.format(name, command))


def test_BOTH_localiser_arms_are_swept_and_not_just_the_default():
    # The hole this file was rewritten for: a pattern set that covers the
    # arm the default brings up and orphans the other.
    commands = [c for _, resolved, _ in stack_spawns() for c in resolved]
    env = config_env()
    for key in ("CFG_LOCALIZATION_AMCL_EXECUTABLE",
                "CFG_LOCALIZATION_SLAM_EXECUTABLE"):
        arm = [c for c in commands if env[key][0] in c.split()]
        assert arm, "no spawned command runs {}".format(env[key][0])


def test_the_localisation_node_is_nominated_by_its_EXECUTABLE():
    # AND NOT BY `slam_toolbox`, WHICH IS DELIBERATE. That package name is
    # also on the OFFLINE mapper's command line - tools/build_map.sh runs
    # sync_slam_toolbox_node on isolation.map_ros_domain_id - and a
    # pattern that nominated it would lean the whole safety of the sweep
    # on ours() rather than on the pattern. ours() would in fact spare it
    # (the replay carries no GZ_PARTITION), and a sweep that is one
    # environment variable away from killing an unrelated build is not
    # the design tools/_common.sh argues for.
    env, known = config_env(), patterns()
    assert env["CFG_LOCALIZATION_SLAM_EXECUTABLE"][0] in known
    assert not [p for p in known
                if p in env["CFG_MAP_SLAM_EXECUTABLE"][0]]


def test_the_two_static_transforms_share_one_pattern():
    # The IMU's mount and the nav lidar's are two processes of one
    # executable; one pattern finds both, which is why there is one.
    assert "static_transform_publisher" in patterns()


def test_no_pattern_is_empty_or_whitespace():
    # An empty pattern matches every process on the machine, and only
    # ours() would then stand between the sweep and the rest of the
    # system.
    for pattern in patterns():
        assert pattern.strip() == pattern and pattern.strip()


def test_every_pattern_still_nominates_something_this_script_starts():
    # THE OTHER DIRECTION, and it is the one that catches a child that was
    # REMOVED. A pattern nominating nothing costs one pgrep and is
    # harmless; it is also the fingerprint of a stale list, and a stale
    # list is what this file exists to prevent in both directions.
    commands = [c for _, resolved, _ in stack_spawns() for c in resolved]
    for pattern in patterns():
        assert any(pattern in c for c in commands), (
            "no child this script spawns carries `{}` on its command "
            "line".format(pattern))


# ----------------------------------------------------------------------
# an arm-specific check belongs inside its arm's guard
# ----------------------------------------------------------------------

def test_the_block_tracker_sees_a_one_line_if():
    rows = {n: c for n, _, c in conditions_at('if [ "$A" = b ]; then x; fi\n')}
    assert rows[1] == ['[ "$A" = b ]']


def test_the_block_tracker_sees_a_multi_line_if():
    text = 'if [ "$A" = b ]; then\n    guarded\nfi\nafter\n'
    rows = {r.strip(): c for _, r, c in conditions_at(text)}
    assert rows["guarded"] == ['[ "$A" = b ]']
    assert rows["after"] == []


def test_a_nested_if_stacks_and_unwinds():
    text = ('if [ "$A" ]; then\n    if [ "$B" ]; then\n'
            '        deep\n    fi\n    shallow\nfi\n')
    rows = {r.strip(): list(c) for _, r, c in conditions_at(text)}
    assert rows["deep"] == ['[ "$A" ]', '[ "$B" ]']
    assert rows["shallow"] == ['[ "$A" ]']


def test_an_else_REPLACES_the_condition_rather_than_nesting_under_it():
    text = 'if [ "$A" ]; then\n    yes\nelse\n    no\nfi\n'
    rows = {r.strip(): list(c) for _, r, c in conditions_at(text)}
    assert rows["yes"] == ['[ "$A" ]']
    assert rows["no"] == ["else"]


def test_the_word_if_INSIDE_A_COMMENT_does_not_open_a_block():
    # This script's prose says `if` and `fi` far more often than its code
    # does; a tracker that counted them would unwind to nonsense by the
    # third paragraph.
    text = ('# what happens if this fails, and how to verify it\n'
            'guarded_by_nothing\n')
    rows = {r.strip(): list(c) for _, r, c in conditions_at(text) if r.strip()}
    assert rows["guarded_by_nothing"] == []


def test_an_unguarded_arm_check_is_what_this_would_have_caught():
    # THE REGRESSION, AS A FIXTURE. Called like this, check_slam_mode
    # refused every amcl bringup: amcl.yaml has no `mode:` line at all.
    text = ('if [ "$LOCALIZE" = true ]; then\n'
            '    check_loc_params "$LOC_PARAMS"\n'
            '    check_slam_mode\n'
            'fi\n')
    assert not [c for _, r, c in conditions_at(text)
                if "check_slam_mode" in r
                and any("SLAM" in one.upper() for one in c)]


def test_every_arm_named_check_is_called_inside_its_arm_guard():
    # A function whose NAME carries an arm label runs code that only that
    # arm can survive, and the other arm reaching it is not a redundant
    # check - it is a refusal on the shipping default. What the guard has
    # to mention is that arm's label; `$CFG_LOCALIZATION_SLAM_LABEL` and
    # the literal both count, because config.yaml owns the value and the
    # script may spell either.
    script = read("m5v3.sh")
    labels = {arm: config_env()["CFG_LOCALIZATION_{}_LABEL".format(
        arm.upper())][0] for arm in ("amcl", "slam")}
    definitions = set(re.findall(r"(?m)^([a-z_]+)\(\) *\{", script))
    arm_named = {name: arm for name in definitions
                 for arm in labels if arm in name.split("_")}
    assert arm_named, "no arm-named check function found to check"
    for number, line, scope in conditions_at(script):
        for name, arm in arm_named.items():
            if not re.search(r"(?<![\w])" + name + r"(?![\w(])", line):
                continue
            wanted = (labels[arm], arm.upper() + "_LABEL")
            assert any(any(w in one for w in wanted) for one in scope), (
                "m5v3.sh:{} calls {}() with nothing in scope naming the "
                "`{}` arm - the conditions here are {}. An arm-specific "
                "check reached from the other arm does not merely pass: "
                "check_slam_mode() refused every `--localize {}` bringup, "
                "because amcl.yaml has no `mode:` line at "
                "all.".format(number, name, arm, scope or "(none)",
                              labels["amcl"]))
