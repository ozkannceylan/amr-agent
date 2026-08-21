"""virtual_fplc.py - a behavioural model of the validated F-PLC program.

`m6.py --virtual` swaps the PLCSIM Advanced API object for an instance
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
  fault on exactly that in-between picture. m6.py reads Motor once
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
    """Duck-types the five PLCSIM API methods m6.py uses."""

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
