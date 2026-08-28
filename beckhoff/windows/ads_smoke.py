# ads_smoke.py - ADS round-trip smoke test for the amr_tc project.
# Mirrors the panel's RESET: write healthy inputs, pulse Acknowledge,
# expect Motor TRUE. WF_Clear stays FALSE on purpose - Motor must not
# depend on it (measured F-CPU law, m5_ver2/step2+step3 PROOF).
import os
import time

os.add_dll_directory(r"C:\Program Files (x86)\Beckhoff\TwinCAT\Common64")
import pyads

NET_ID = "127.0.0.1.1.1"   # local user-mode runtime
PORT = 851                  # TC3 PLC runtime 1

plc = pyads.Connection(NET_ID, PORT)
plc.open()

print("ads_state:", plc.read_state())  # (5, ...) = Run
case_b0 = plc.read_by_name("GVL_IO.CASE_B0", pyads.PLCTYPE_BOOL)
print(f"CASE_B0={case_b0}  (MAIN sets TRUE every cycle; False = MAIN never runs)")

motor0 = plc.read_by_name("GVL_IO.Motor", pyads.PLCTYPE_BOOL)
vlimit0 = plc.read_by_name("GVL_IO.V_Limit", pyads.PLCTYPE_INT)
print(f"boot:   Motor={motor0} V_Limit={vlimit0}  (expect False 300, born latched)")

for tag in ("EStop", "PF_OSSD", "PF_OSSD_right", "PF_OSSD_left"):
    plc.write_by_name(f"GVL_IO.{tag}", True, pyads.PLCTYPE_BOOL)

motor1 = plc.read_by_name("GVL_IO.Motor", pyads.PLCTYPE_BOOL)
print(f"healthy, no ack: Motor={motor1}  (expect False - a demand latches)")

plc.write_by_name("GVL_IO.Acknowledge", False, pyads.PLCTYPE_BOOL)
time.sleep(0.1)
plc.write_by_name("GVL_IO.Acknowledge", True, pyads.PLCTYPE_BOOL)
time.sleep(0.1)

motor2 = plc.read_by_name("GVL_IO.Motor", pyads.PLCTYPE_BOOL)
print(f"after RESET edge: Motor={motor2}  (expect True)")

# trip: press the e-stop, then ack again without releasing -> must stay False
plc.write_by_name("GVL_IO.EStop", False, pyads.PLCTYPE_BOOL)
time.sleep(0.05)
motor3 = plc.read_by_name("GVL_IO.Motor", pyads.PLCTYPE_BOOL)
plc.write_by_name("GVL_IO.EStop", True, pyads.PLCTYPE_BOOL)
plc.write_by_name("GVL_IO.Acknowledge", False, pyads.PLCTYPE_BOOL)
time.sleep(0.1)
plc.write_by_name("GVL_IO.Acknowledge", True, pyads.PLCTYPE_BOOL)
time.sleep(0.1)
motor4 = plc.read_by_name("GVL_IO.Motor", pyads.PLCTYPE_BOOL)
print(f"estop demand: Motor={motor3} (expect False); healthy+ack again: Motor={motor4} (expect True)")

plc.close()
print("PASS" if (not motor0 and vlimit0 == 300 and not motor1
                 and motor2 and not motor3 and motor4) else "FAIL")
