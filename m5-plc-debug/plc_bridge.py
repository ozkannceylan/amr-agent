import sys, clr, json, socket, threading, time
sys.path.append(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0")
clr.AddReference("Siemens.Simatic.Simulation.Runtime.Api.x64")
from Siemens.Simatic.Simulation.Runtime import SimulationRuntimeManager, ETagListDetails

plc = SimulationRuntimeManager.CreateInterface("PLC_2")
plc.UpdateTagList(ETagListDetails.IOM)

ESTOP = [True]; ACK_UNTIL = [0.0]
def stdin_reader():
    print("komutlar: e0 | e1 | a")
    while True:
        c = input().strip().lower()
        if   c == "e0": ESTOP[0] = False
        elif c == "e1": ESTOP[0] = True
        elif c == "a":  ACK_UNTIL[0] = time.time() + 0.3
threading.Thread(target=stdin_reader, daemon=True).start()

def udp_rx(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", port)); s.setblocking(False); return s
rx_s, rx_e = udp_rx(5006), udp_rx(5009)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

pf = wf = False; a = b = 9999; t_s = t_e = 0.0
def drain(sock):
    last = None
    try:
        while True: last = json.loads(sock.recv(128).decode())
    except BlockingIOError: pass
    return last

try:
    while True:
        now = time.time()
        m = drain(rx_s)
        if m: pf, wf, t_s = m["pf"], m["wf"], now
        m = drain(rx_e)
        if m: a, b, t_e = m["a"], m["b"], now
        if now - t_s > 0.3: pf = wf = False        # tarayici sustu
        if now - t_e > 0.3: a = b = 9999           # enkoder sustu -> asiri hiz gibi davran
        plc.WriteBool("PF_OSSD", pf); plc.WriteBool("WF_Clear", wf)
        plc.WriteInt16("ENC_A", a);   plc.WriteInt16("ENC_B", b)
        plc.WriteBool("E-Stop", ESTOP[0])
        plc.WriteBool("Acknowledge", time.time() < ACK_UNTIL[0])
        case = (1 if plc.ReadBool("CASE_B0") else 0) + (2 if plc.ReadBool("CASE_B1") else 0)
        tx.sendto(json.dumps({"case": case}).encode(), ("127.0.0.1", 5008))
        sto = plc.ReadBool("Motor"); vlim = plc.ReadInt16("V_Limit")
        # print(f"pf={pf} wf={wf} enc={a}/{b} case={case} es={ESTOP[0]} | STO={sto} V={vlim}   ", end="\r")
        time.sleep(0.02)
finally:
    for t in ("PF_OSSD", "WF_Clear", "E-Stop"): plc.WriteBool(t, False)