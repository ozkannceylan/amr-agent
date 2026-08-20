# Virtual F-PLC (`--virtual`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `step5.py --virtual` runs the sole PLC writer without PLCSIM Advanced by swapping the API object for an in-process behavioural model of the validated F-program.

**Architecture:** One new file, `m5_ver2/step5/windows/virtual_fplc.py`, duck-types the five PLCSIM API methods step5.py uses. `connect_plc()` branches on a module-level `VIRTUAL` flag; nothing else in the loop, panel or fail-safe path changes. Spec: `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md` — read it before starting.

**Tech Stack:** Plain Python 3 (no package, no colcon), pytest. The virtual branch must import no Siemens/pythonnet/Tk code.

## Global Constraints

- Under 150 lines per file (`m5_ver2/CLAUDE.md`).
- Never rename or invent a PLC tag; names are case-sensitive and may contain hyphens (`E-Stop`).
- Steps 1–4 are frozen copies — touch nothing outside `m5_ver2/step5/`.
- The 5100/5101 wire payloads must not change; the WSL side must be unable to tell virtual from real.
- Without `--virtual`, `step5.py` behaviour must be byte-identical to today (the non-virtual code path may not change except the four edits listed in Task 2).
- Everything the model shows the user says "VIRTUAL F-PLC (model)" — it claims no safety integrity.
- Commit messages: lowercase `step5: ...` style, no attribution lines, no Claude mention.

## The model's contract (from the spec — normative for both tasks)

- Five latching ESTOP1 instances: `estop`, `pf`, `pf_right`, `pf_left`, `speed`. A demand (unhealthy input) latches. Healing alone never re-enables. A rising edge on `Acknowledge` clears every latch whose input is healthy at that moment. All five start latched (ACK_NEC: one ack owed after startup). `Motor` = no latch set.
- `speed` is healthy iff `|ENC_A - ENC_B| <= 50` AND `max(|A|,|B|) <= 2800` AND `max(|A|,|B|) <= V_Limit`.
- `V_Limit` = 1500 if `WF_Clear`, `WF_Clear_right`, `WF_Clear_left` are all True, else 300 (owner ruling 2026-08-20).
- Case bits pinned: `CASE_B0=True`, `CASE_B1=False` (case 1).
- **Cycle boundary = a `ReadBool("Motor")` call.** Writes only store values; the scan (latching + ack edge) runs when `Motor` is read. This mirrors the F-cycle sampling the process image once per cycle, so the writer's non-atomic write sequence (ENC_A then ENC_B) can never trip the cross-check on a half-written picture. step5.py reads `Motor` exactly once per 20 ms cycle, first among the outputs.
- Reading an input tag returns the last written value (the process image). Unknown tags raise `KeyError` — fail loud, never guess.

---

### Task 1: The model and its tests

**Files:**
- Create: `m5_ver2/step5/tests/test_virtual_fplc.py`
- Create: `m5_ver2/step5/windows/virtual_fplc.py`

**Interfaces:**
- Consumes: nothing (pure Python; `tests/conftest.py` already puts `windows/` on `sys.path`).
- Produces: `class VirtualFPLC` with methods `UpdateTagList(*args) -> None`, `WriteBool(tag: str, value: bool) -> None`, `WriteInt16(tag: str, value: int) -> None`, `ReadBool(tag: str) -> bool`, `ReadInt16(tag: str) -> int`. Task 2 imports it as `from virtual_fplc import VirtualFPLC`.

- [ ] **Step 1: Write the failing test file**

`m5_ver2/step5/tests/test_virtual_fplc.py`, exactly:

```python
"""virtual_fplc.py's model semantics. Nothing here needs PLCSIM or Tk.

Every behaviour asserted below is measured live (m5_ver2/CLAUDE.md
section 3.2, the step PROOFs) or an owner ruling recorded in
docs/superpowers/specs/2026-08-20-virtual-fplc-design.md. The cycle
boundary is a ReadBool("Motor") call, so the helpers read Motor to
advance the model exactly as step5.py's 20 ms loop does.
"""
import pytest

from virtual_fplc import VirtualFPLC

SCANNERS = ("PF_OSSD", "PF_OSSD_right", "PF_OSSD_left")
WARNINGS = ("WF_Clear", "WF_Clear_right", "WF_Clear_left")


def write_healthy(plc, enc=(0, 0)):
    """One cycle's input picture, everything healthy, ack released."""
    for tag in SCANNERS + WARNINGS:
        plc.WriteBool(tag, True)
    plc.WriteInt16("ENC_A", enc[0])
    plc.WriteInt16("ENC_B", enc[1])
    plc.WriteBool("E-Stop", True)
    plc.WriteBool("Acknowledge", False)


def ack(plc):
    """An Acknowledge rising edge with a cycle boundary inside it."""
    plc.WriteBool("Acknowledge", True)
    plc.ReadBool("Motor")
    plc.WriteBool("Acknowledge", False)


def enabled_plc():
    plc = VirtualFPLC()
    write_healthy(plc)
    ack(plc)
    assert plc.ReadBool("Motor") is True
    return plc


def test_startup_needs_one_ack_before_motor():
    plc = VirtualFPLC()
    write_healthy(plc)
    assert plc.ReadBool("Motor") is False    # ACK_NEC
    ack(plc)
    assert plc.ReadBool("Motor") is True


@pytest.mark.parametrize("tag", ("E-Stop",) + SCANNERS)
def test_each_demand_latches_and_healing_does_not_reenable(tag):
    plc = enabled_plc()
    plc.WriteBool(tag, False)
    assert plc.ReadBool("Motor") is False
    plc.WriteBool(tag, True)
    assert plc.ReadBool("Motor") is False    # latched
    ack(plc)
    assert plc.ReadBool("Motor") is True


def test_one_ack_clears_every_healthy_latch():
    plc = enabled_plc()
    plc.WriteBool("E-Stop", False)
    for tag in SCANNERS:
        plc.WriteBool(tag, False)
    assert plc.ReadBool("Motor") is False
    write_healthy(plc)
    ack(plc)
    assert plc.ReadBool("Motor") is True


def test_ack_skips_a_latch_whose_input_is_still_unhealthy():
    plc = enabled_plc()
    plc.WriteBool("PF_OSSD_left", False)
    ack(plc)                                 # consumed while unhealthy
    assert plc.ReadBool("Motor") is False
    plc.WriteBool("PF_OSSD_left", True)
    assert plc.ReadBool("Motor") is False
    ack(plc)
    assert plc.ReadBool("Motor") is True


def test_holding_acknowledge_is_one_edge_not_many():
    plc = enabled_plc()
    plc.WriteBool("Acknowledge", True)
    plc.ReadBool("Motor")                    # edge consumed here
    plc.WriteBool("PF_OSSD", False)
    plc.ReadBool("Motor")                    # demand latches
    plc.WriteBool("PF_OSSD", True)
    assert plc.ReadBool("Motor") is False    # still held: no new edge


def test_cross_check_trips_above_50():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 100)
    plc.WriteInt16("ENC_B", 160)
    assert plc.ReadBool("Motor") is False


def test_disagreement_of_exactly_50_is_allowed():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 100)
    plc.WriteInt16("ENC_B", 150)
    assert plc.ReadBool("Motor") is True


def test_half_written_encoder_pair_does_not_trip():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 500)             # B still 0: no read, no scan
    plc.WriteInt16("ENC_B", 500)
    assert plc.ReadBool("Motor") is True


def test_ceiling_2800_by_magnitude_either_direction():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", -2850)
    plc.WriteInt16("ENC_B", -2850)
    assert plc.ReadBool("Motor") is False


def test_speed_above_v_limit_trips_when_any_wf_violated():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 500)
    plc.WriteInt16("ENC_B", 500)
    assert plc.ReadBool("Motor") is True     # 500 < 1500
    plc.WriteBool("WF_Clear_left", False)    # any-WF ruling: limit 300
    assert plc.ReadBool("Motor") is False


def test_dead_link_picture_0_3000_trips():
    plc = enabled_plc()
    plc.WriteInt16("ENC_A", 0)
    plc.WriteInt16("ENC_B", 3000)
    assert plc.ReadBool("Motor") is False


@pytest.mark.parametrize("wf", WARNINGS)
def test_v_limit_is_300_when_any_single_wf_is_violated(wf):
    plc = VirtualFPLC()
    write_healthy(plc)
    assert plc.ReadInt16("V_Limit") == 1500
    plc.WriteBool(wf, False)
    assert plc.ReadInt16("V_Limit") == 300


def test_case_bits_are_pinned_at_case_1():
    plc = VirtualFPLC()
    assert plc.ReadBool("CASE_B0") is True
    assert plc.ReadBool("CASE_B1") is False


def test_input_readback_returns_the_process_image():
    plc = VirtualFPLC()
    plc.WriteBool("E-Stop", True)
    assert plc.ReadBool("E-Stop") is True
    plc.WriteBool("E-Stop", False)
    assert plc.ReadBool("E-Stop") is False


def test_unknown_tags_raise_keyerror():
    plc = VirtualFPLC()
    with pytest.raises(KeyError):
        plc.WriteBool("NoSuchTag", True)
    with pytest.raises(KeyError):
        plc.ReadBool("NoSuchTag")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (Windows, repo root): `python -m pytest m5_ver2/step5/tests/test_virtual_fplc.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'virtual_fplc'`.

- [ ] **Step 3: Write the model**

`m5_ver2/step5/windows/virtual_fplc.py`, exactly:

```python
"""virtual_fplc.py - a behavioural model of the validated F-PLC program.

`step5.py --virtual` swaps the PLCSIM Advanced API object for an instance
of this class. It is a TEST RIG, not the F-program: every response
reproduces behaviour measured live (m5_ver2/CLAUDE.md section 3.2, the
step PROOFs) or an owner ruling recorded in
docs/superpowers/specs/2026-08-20-virtual-fplc-design.md. It claims no
safety integrity.

THE TWO RULINGS BAKED IN (owner, 2026-08-20)
  V_Limit is 300 when ANY of the three warning fields is violated, else
  1500 - the live composition with the right/left warning fields was
  contradictory and never resolved TIA-side, so the model takes the
  envelope that errs slow. The monitoring case is pinned at 1, the value
  every live Step 5 run reported.

WHY THE SCAN RUNS ON ReadBool("Motor") AND NOT ON EVERY WRITE
  The real F-cycle samples the process image once per cycle, so it can
  never see the writer's half-written encoder pair (ENC_A stored, ENC_B
  not yet). A scan on every write would latch a phantom cross-check
  fault on exactly that in-between picture. step5.py reads Motor once
  per 20 ms cycle, first among the outputs - that read IS the cycle.

WHY DEMANDS LATCH
  ESTOP1 semantics, measured: an unhealthy input latches its instance
  and healing alone does not re-enable. A rising edge on Acknowledge
  clears every latch whose input is healthy at that moment, and one ack
  after startup is owed before Motor can ever be True (ACK_NEC).
  Motor is the AND of the five enables.
"""

CROSS_CHECK_MM_S = 50    # |ENC_A - ENC_B| beyond this is a fault
CEILING_MM_S = 2800      # either channel's magnitude beyond this is a fault
V_LIMIT_CLEAR = 1500     # all three warning fields clear
V_LIMIT_VIOLATED = 300   # any warning field violated (ruling 2026-08-20)

_BOOL_INPUTS = ("E-Stop", "PF_OSSD", "WF_Clear", "PF_OSSD_right",
                "WF_Clear_right", "PF_OSSD_left", "WF_Clear_left",
                "Acknowledge")
_INT_INPUTS = ("ENC_A", "ENC_B")
_INSTANCES = ("estop", "pf", "pf_right", "pf_left", "speed")


class VirtualFPLC:
    """Duck-types the five PLCSIM API methods step5.py uses."""

    def __init__(self):
        self._bools = {tag: False for tag in _BOOL_INPUTS}
        self._ints = {tag: 0 for tag in _INT_INPUTS}
        # ACK_NEC: everything starts latched; one ack is owed at startup.
        self._latched = dict.fromkeys(_INSTANCES, True)
        self._prev_ack = False

    # ------------------------- the API surface -------------------------
    def UpdateTagList(self, *_args):
        pass

    def WriteBool(self, tag, value):
        if tag not in self._bools:
            raise KeyError(tag)
        self._bools[tag] = bool(value)

    def WriteInt16(self, tag, value):
        if tag not in self._ints:
            raise KeyError(tag)
        self._ints[tag] = int(value)

    def ReadBool(self, tag):
        if tag == "Motor":
            self._scan()
            return not any(self._latched.values())
        if tag == "CASE_B0":
            return True      # monitoring case pinned at 1 (binary 01)
        if tag == "CASE_B1":
            return False
        return self._bools[tag]    # inputs read back the process image

    def ReadInt16(self, tag):
        if tag == "V_Limit":
            return self._v_limit()
        return self._ints[tag]

    # --------------------------- the model -----------------------------
    def _v_limit(self):
        clear = all(self._bools[t] for t in
                    ("WF_Clear", "WF_Clear_right", "WF_Clear_left"))
        return V_LIMIT_CLEAR if clear else V_LIMIT_VIOLATED

    def _healthy(self):
        a, b = self._ints["ENC_A"], self._ints["ENC_B"]
        top = max(abs(a), abs(b))
        return {
            "estop": self._bools["E-Stop"],
            "pf": self._bools["PF_OSSD"],
            "pf_right": self._bools["PF_OSSD_right"],
            "pf_left": self._bools["PF_OSSD_left"],
            "speed": (abs(a - b) <= CROSS_CHECK_MM_S
                      and top <= CEILING_MM_S
                      and top <= self._v_limit()),
        }

    def _scan(self):
        healthy = self._healthy()
        for name, ok in healthy.items():
            if not ok:
                self._latched[name] = True         # a demand latches
        ack = self._bools["Acknowledge"]
        if ack and not self._prev_ack:             # rising edge only
            for name, ok in healthy.items():
                if ok:
                    self._latched[name] = False
        self._prev_ack = ack
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest m5_ver2/step5/tests/test_virtual_fplc.py -q`
Expected: all pass (20 tests: 13 plain functions plus one parametrize x4 and one x3). Also confirm the line budget: `wc -l m5_ver2/step5/windows/virtual_fplc.py` must be under 150.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step5/windows/virtual_fplc.py m5_ver2/step5/tests/test_virtual_fplc.py
git commit -m "step5: the virtual F-PLC model - measured semantics, unit-tested"
```

---

### Task 2: Wire `--virtual` into the writer, note it in the docs

**Files:**
- Modify: `m5_ver2/step5/windows/step5.py` (four edits, nothing else)
- Modify: `m5_ver2/step5/README_step5.md`
- Modify: `m5_ver2/step5/CONTEXT.md`

**Interfaces:**
- Consumes: `from virtual_fplc import VirtualFPLC` (Task 1; same directory as step5.py, so the script import works, and `tests/conftest.py` already has the path).
- Produces: `step5.py --virtual` — the flag is the whole public interface.

- [ ] **Step 1: Baseline the existing suite**

Run: `wsl -e bash -lc "source /opt/ros/jazzy/setup.bash && cd /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step5 && python3 -m pytest tests/ -q"`
Record the pass/fail count. Your edits must not change it (Task 1's new file will already be included and passing).

- [ ] **Step 2: The four step5.py edits**

Edit 1 — usage lines at the bottom of the module docstring. Old:

```
Usage (Windows, 64-bit Python, PLCSIM Advanced already in RUN):
  python m5_ver2\step5\windows\step5.py
```

New (keep the backslash style exactly as found in the file):

```
Usage (Windows, 64-bit Python, PLCSIM Advanced already in RUN):
  python m5_ver2\step5\windows\step5.py
With no PLCSIM license (any Python, no pythonnet):
  python m5_ver2\step5\windows\step5.py --virtual
```

Edit 2 — in the CONFIG block, directly under `PLC_INSTANCE = "PLC_2"`:

```python
VIRTUAL = "--virtual" in sys.argv  # no PLCSIM: virtual_fplc.py plays the F-PLC
```

Edit 3 — top of `connect_plc()`, before `sys.path.append(API_DLL_DIR)`:

```python
def connect_plc():
    """CreateInterface, with the -4 case reported rather than worked around."""
    if VIRTUAL:
        from virtual_fplc import VirtualFPLC
        print("VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop")
        return VirtualFPLC()
    sys.path.append(API_DLL_DIR)
```

Edit 4 — the panel title. Old: `root.title("Forklift 1 PLC Control Panel")`. New:

```python
    root.title("Forklift 1 PLC Control Panel"
               + (" - VIRTUAL F-PLC (model)" if VIRTUAL else ""))
```

- [ ] **Step 3: Headless smoke of the branch**

Run (repo root; try on Windows AND once via WSL — the virtual branch must work on both):

```bash
python -c "import sys; sys.argv.append('--virtual'); sys.path.insert(0, 'm5_ver2/step5/windows'); import step5; plc = step5.connect_plc(); print(type(plc).__name__, plc.ReadInt16('V_Limit'))"
```

Expected output: the `VIRTUAL F-PLC (model) - ...` line, then `VirtualFPLC 300` (300 because nothing healthy has been written yet). No Siemens import error, no Tk window.

- [ ] **Step 4: The two doc notes**

`README_step5.md` — immediately after the launch table containing the `python m5_ver2\step5\windows\step5.py` row, add:

```markdown
**No PLCSIM license?** Run step 7 as `python m5_ver2\step5\windows\step5.py --virtual`
and skip step 1 entirely: `windows/virtual_fplc.py` plays the F-PLC in-process with
the measured semantics (design: `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md`).
The panel titles itself `VIRTUAL F-PLC (model)`; results earned this way are rig
results, not F-program validation.
```

`CONTEXT.md` — insert a new section directly above `## Known debt carried forward`:

```markdown
## The virtual F-PLC rig (2026-08-20)

The PLCSIM Advanced trial expired. `windows/step5.py --virtual` swaps the API
object for `windows/virtual_fplc.py` — a behavioural model of the validated
F-program: five latching ESTOP1 instances, ack-edge semantics, the encoder
cross-check and ceiling, `V_Limit` and the pinned monitoring case. Two owner
rulings are baked in (any violated warning field → `V_Limit` 300; case pinned
at 1) — see `docs/superpowers/specs/2026-08-20-virtual-fplc-design.md`.
Without the flag the writer still expects PLCSIM `PLC_2`, unchanged. The model
claims no safety integrity: a Step 6 result earned on this rig is a rig result
until re-proved against a real or licensed PLC.
```

- [ ] **Step 5: Re-run the full suite, compare to the baseline**

Run the same WSL command as Step 1. Expected: identical pass/fail counts plus the 20 `test_virtual_fplc.py` passes; zero new failures. Also confirm `git diff m5_ver2/step5/windows/step5.py` shows exactly the four edits and nothing else.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step5/windows/step5.py m5_ver2/step5/README_step5.md m5_ver2/step5/CONTEXT.md
git commit -m "step5: --virtual wires the model into the writer; the docs name the rig"
```
