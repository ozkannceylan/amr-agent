// FB_ESTOP1 - the Siemens ESTOP1 semantics, ported to structured text.
//
// ROLE AND CLAIM, stated here because this file is where the logic lives:
// the safety chain is AUTHORED as a TE9000 safety project - the spec is
// beckhoff/plc/safety/SAFETY-APP.md - and this block is its STAND-IN
// EXECUTOR for the live loop until a safety runtime (TE9100 or TwinSAFE
// hardware) lands. It demonstrates the same observable semantics the
// F-block showed on PLCSIM Advanced; it carries NO safety integrity, no
// PL, Category, SIL or PFH (RESEARCH.md D3; ADR 0011 D5 discipline). The
// parity table (RUNBOOK part 5, S1-S6) pins it to the safety project.
//
// The semantics, measured on the F-CPU (m5_ver2/CLAUDE.md section 3.2):
//   - a demand LATCHES: the input returning to healthy does not re-enable
//   - clearing needs a RISING EDGE on Acknowledge, with the input healthy
//   - ACK_NEC: one Acknowledge is required after startup before Q can
//     ever be TRUE - hence demandLatched starts TRUE
//
// Paste into: PLC project > POUs > Add > POU, Function Block, ST.
FUNCTION_BLOCK FB_ESTOP1
VAR_INPUT
    S_In : BOOL;   // TRUE = healthy; FALSE = demand
    Ack  : BOOL;   // acknowledge button
END_VAR
VAR_OUTPUT
    Q : BOOL;      // enable: TRUE only with input healthy and no latch
END_VAR
VAR
    demandLatched : BOOL := TRUE;   // ACK_NEC: born latched, every startup
    ackPrev       : BOOL := TRUE;   // TRUE so a stuck-high Ack at startup
                                    // cannot count as an edge
END_VAR

IF NOT S_In THEN
    demandLatched := TRUE;                    // a demand latches
END_IF;
IF Ack AND NOT ackPrev AND S_In THEN
    demandLatched := FALSE;                   // rising edge, input healthy
END_IF;
ackPrev := Ack;
Q := S_In AND NOT demandLatched;
