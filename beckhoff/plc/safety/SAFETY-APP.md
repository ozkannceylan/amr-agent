# The TE9000 safety application — design, block by block

**This document is the safety implementation's specification.** The chain is
authored as a real TwinSAFE safety project in the TE9000 Safety Editor
(FBD, certified function blocks, target EL6910); the ST files one directory
up are its **stand-in executor** for the live loop until a safety runtime
(TE9100 or TwinSAFE hardware) is present — see RESEARCH.md D3. The safety
project file itself (`.splc`/editor artifacts) is created in the editor per
RUNBOOK part 3 and committed from the owner's machine once verified; this
spec is what it is built from and reviewed against.

## Identity

| Item | Value |
|---|---|
| Editor | TE9000 TwinCAT 3 Safety Editor (FBD) |
| Target system | **EL6910** — the editor's hardware-less debug explicitly does not work for the older EL6900 target |
| Template | Safety project *with ErrAck and Run mappings* |
| Simulation | Target as *External Device* (simulated); alias devices EL1904-class inputs, EL2904-class output |
| Source of semantics | The measured F-CPU behaviour, m5_ver2/CLAUDE.md §3.2 |

## Alias devices (inputs and outputs of the safety world)

| Alias | Class | Carries | In simulation fed by |
|---|---|---|---|
| AI_EStop | EL1904 ch | e-stop NC chain, TRUE = healthy | panel → GVL_IO.EStop |
| AI_PF_Back | EL1904 ch | back OSSD pair, TRUE = clear | panel → GVL_IO.PF_OSSD |
| AI_PF_Right | EL1904 ch | right OSSD pair | panel → GVL_IO.PF_OSSD_right |
| AI_PF_Left | EL1904 ch | left OSSD pair | panel → GVL_IO.PF_OSSD_left |
| AI_WF_Back / _Right / _Left | EL1904 ch | warning fields, TRUE = clear | panel → GVL_IO.WF_Clear* |
| AI_ENC_A, AI_ENC_B | analog in | encoder channels, mm/s | panel → GVL_IO.ENC_A/B |
| AQ_MotorEnable | EL2904 ch | **the** drive enable | mirrored → GVL_IO.Motor |
| Std-PLC mapping | non-safe | Acknowledge (restart), ErrAck | GVL_IO.Acknowledge |

The 1oo2 channel pairs collapse to one signal in simulation, exactly as
PLCSIM collapsed the F-DI pairs to one process-image bit — same modelling
boundary, stated the same way.

## Networks

**N1–N4 — the latching stop chains.** Four `safeEstop` instances (the
certified block monitors two-channel e-stop circuits and carries the
restart behaviour):

| Instance | EStopIn | Restart | Semantics required |
|---|---|---|---|
| FB_EStop | AI_EStop | Acknowledge | a demand latches; input healthy does **not** re-enable; restart is a rising edge; one restart required after startup (the ACK_NEC behaviour) |
| FB_PF_Back | AI_PF_Back | Acknowledge | same |
| FB_PF_Right | AI_PF_Right | Acknowledge | same |
| FB_PF_Left | AI_PF_Left | Acknowledge | same |

One shared Acknowledge clears all latches whose input is healthy — the
live F-CPU behaved exactly so (measured 2026-08-13: a single Acknowledge
cleared the right and left latches together).

**N5 — the speed monitor.** Built from the EL6910 set's analog
comparison/limit blocks (consult the EL6910 FB documentation for the exact
block names available in the installed editor version; the *logic* is
fixed here):

```
demand :=    |ENC_A − ENC_B| > 50            (cross-check)
          OR |ENC_A| > 2800  OR |ENC_B| > 2800   (ceiling)
          OR |ENC_A| > limit OR |ENC_B| > limit  (case ceiling)
limit  :=    1500 when (WF_Back AND WF_Right AND WF_Left) else 300
```

The case limit is derived **inside the safety application** from the safe
warning-field inputs — a safety decision must not import a non-safe limit
value. (The standard program still computes `GVL_IO.V_Limit` for the
vehicle's wire, as TIA's standard OB1 did; the two derivations are pinned
to each other by the parity check, RUNBOOK part 5.) `NOT demand` feeds a
fifth latching stage with the shared Acknowledge, like N1–N4.

**N6 — the enable.** `AQ_MotorEnable := AND` of the five chain outputs.
`WF_*` inputs appear **only** in N5's limit derivation — the warning
fields are deliberately NOT in the enable AND, the measured F-CPU law
(Motor TRUE with WF FALSE, step2/step3 PROOF).

## Port choices carried from RESEARCH.md D4 (labelled, fall to validation)

1. Right/left WF composition into the limit: conservative AND (TIA-side
   rule unmapped — step5 PROOF open item 4).
2. Case selection: constant case 1 on the wire (every live step5 run
   observed it); the case bits stay a standard-program output.
3. Case-ceiling margin: the ST stand-in adds +50 mm/s against
   measurement-noise chatter; the safety app uses the same figure so the
   parity check can be exact.

## What may and may not be claimed

The verified safety project demonstrates **certified-block safety logic,
authored and verified in the vendor's safety toolchain, executing in the
editor's documented offline simulation**. Until it runs on a safety
runtime (TE9100 — product-announcement status, quoted 2026-08-15 — or
TwinSAFE hardware), the live loop is executed by the ST stand-in and the
system's words remain "models the F-behaviour, no safety integrity, no
PL/Category/SIL/PFH" (ADR 0011 D5 discipline; ADR 0013 D2 asymmetry,
stated and dated).
