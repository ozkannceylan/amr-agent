// MAIN - the m5_ver2 safety-program behaviour on the standard runtime.
//
// Motor is the AND of five FB_ESTOP1 enables: e-stop button, three
// protective fields (back / right / left - the owner added right and left
// on 2026-08-12), and the speed monitor. WF_Clear is deliberately NOT in
// the Motor AND - measured on the F-CPU (step2/step3 PROOF: Motor TRUE
// with WF FALSE); it gates V_Limit, and through it the speed monitor.
//
// TWO TIA-SIDE BEHAVIOURS WERE NEVER MAPPED AND ARE PORTED CONSERVATIVELY,
// both labelled here and falling to the validation diff (RUNBOOK part 4):
//   - right/left warning-field composition into V_Limit (step5 PROOF open
//     item 4): ported as the conservative AND - ANY warning field occupied
//     drops the ceiling to 300.
//   - monitoring-case selection: ported as the constant case 1, the value
//     every live step5 run observed (case-1 fields 1.0 m / 2.5 m).
//
// Paste into: PLC project > POUs > MAIN (PRG), ST. Default PlcTask (10 ms).
PROGRAM MAIN
VAR
    chainEStop   : FB_ESTOP1;   // e-stop button
    chainPFBack  : FB_ESTOP1;   // back protective field
    chainPFRight : FB_ESTOP1;
    chainPFLeft  : FB_ESTOP1;
    chainSpeed   : FB_ESTOP1;   // encoder cross-check + ceilings
    speedHealthy : BOOL;
    diff         : INT;
    wfAllClear   : BOOL;
END_VAR

// V_Limit first: the speed monitor reads it this same cycle.
// 1500 with the warning fields clear, 300 otherwise - the measured law
// (step3 PROOF: creep demanded 0.68 s after enable near racking).
wfAllClear := GVL_IO.WF_Clear AND GVL_IO.WF_Clear_right
              AND GVL_IO.WF_Clear_left;
IF wfAllClear THEN
    GVL_IO.V_Limit := 1500;
ELSE
    GVL_IO.V_Limit := 300;
END_IF;

// The two-channel speed monitor, all three measured demands:
//   cross-check   |ENC_A - ENC_B| > 50 mm/s   (the fa/oa faults trip this)
//   ceiling       |ENC| > 2800 mm/s
//   case ceiling  |ENC| > V_Limit + 50        (the step3 creep trap)
// The +50 mm/s margin on the case ceiling is the PORT'S choice, labelled:
// the autopilot caps its command AT V_Limit, so the shaft rides exactly on
// the limit and a zero-margin compare would latch on measurement noise.
// The TIA implementation's own tolerance/delay was never mapped; this
// margin is the smallest that cannot chatter, and it falls to the
// validation diff like the other two unmapped behaviours.
diff := ABS(GVL_IO.ENC_A - GVL_IO.ENC_B);
speedHealthy := (diff <= 50)
    AND (ABS(GVL_IO.ENC_A) <= 2800) AND (ABS(GVL_IO.ENC_B) <= 2800)
    AND (ABS(GVL_IO.ENC_A) <= GVL_IO.V_Limit + 50)
    AND (ABS(GVL_IO.ENC_B) <= GVL_IO.V_Limit + 50);

// Five chains, one Acknowledge - the panel's RESET pulse clears them all,
// which is what the live F-CPU did too (measured 2026-08-13: a single
// Acknowledge cleared the right and left latches together).
chainEStop(S_In := GVL_IO.EStop, Ack := GVL_IO.Acknowledge);
chainPFBack(S_In := GVL_IO.PF_OSSD, Ack := GVL_IO.Acknowledge);
chainPFRight(S_In := GVL_IO.PF_OSSD_right, Ack := GVL_IO.Acknowledge);
chainPFLeft(S_In := GVL_IO.PF_OSSD_left, Ack := GVL_IO.Acknowledge);
chainSpeed(S_In := speedHealthy, Ack := GVL_IO.Acknowledge);

GVL_IO.Motor := chainEStop.Q AND chainPFBack.Q AND chainPFRight.Q
                AND chainPFLeft.Q AND chainSpeed.Q;

// Case bits: 01 = case 1, pinned (see the header). The vehicle's
// field_eval maps an unreadable 00 to case 3, the largest field - that
// fail direction lives on the consumer and is not re-implemented here.
GVL_IO.CASE_B0 := TRUE;
GVL_IO.CASE_B1 := FALSE;
