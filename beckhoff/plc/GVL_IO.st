// GVL_IO - the port of the m5_ver2 tag table (m5_ver2/CLAUDE.md section 3.1).
// One global variable list, written over ADS by exactly one process
// (beckhoff/windows/step5_tc.py) - the single-writer rule carries over.
//
// NAME MAPPING, the only one in the port: ST identifiers cannot carry a
// hyphen, so the Siemens tag `E-Stop` is `EStop` here. The UDP wire keys
// toward WSL are byte-identical to the m5_ver2 wire; the mapping lives in
// the writer's TAG table and nowhere else.
//
// Paste into: PLC project > GVLs > Add > Global Variable List, name GVL_IO.
{attribute 'qualified_only'}
VAR_GLOBAL
    // ---- written by the panel (the field devices' picture) ----
    EStop          : BOOL := FALSE;  // TRUE = healthy (NC chain closed)
    PF_OSSD        : BOOL := FALSE;  // TRUE = back protective field clear
    WF_Clear       : BOOL := FALSE;  // TRUE = back warning field clear
    PF_OSSD_right  : BOOL := FALSE;
    WF_Clear_right : BOOL := FALSE;
    PF_OSSD_left   : BOOL := FALSE;
    WF_Clear_left  : BOOL := FALSE;
    Acknowledge    : BOOL := FALSE;  // reset button, rising edge required
    ENC_A          : INT  := 0;      // encoder channel A, mm/s
    ENC_B          : INT  := 0;      // encoder channel B, mm/s

    // ---- computed by MAIN, read by the panel ----
    Motor          : BOOL := FALSE;  // the drive enable, AND of all chains
    CASE_B0        : BOOL := FALSE;  // monitoring-case bit 0
    CASE_B1        : BOOL := FALSE;  // monitoring-case bit 1
    V_Limit        : INT  := 300;    // speed ceiling mm/s; starts at creep -
                                     // not knowing is the slowest permission
END_VAR
