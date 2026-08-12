import socket, json

FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3

def field(d, clear, cnt, th):
    raw = d > (th if clear else th + 0.2)                 # +0.2 m histerezis
    cnt = cnt + 1 if raw != clear else 0
    return (raw, 0) if cnt >= N_SCAN else (clear, cnt)

rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx.bind(("127.0.0.1", 5005)); rx.settimeout(0.3)
rc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rc.bind(("127.0.0.1", 5008)); rc.setblocking(False)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
pf = wf = False; pfc = wfc = 0; case = 3                  # bilinmeyen = en buyuk alan

while True:
    try:
        while True: case = json.loads(rc.recv(64).decode()).get("case") or 3
    except BlockingIOError: pass
    if case not in FIELDS: case = 3
    pf_th, wf_th = FIELDS[case]
    try:
        d = float(json.loads(rx.recv(128).decode())["d"])
        pf, pfc = field(d, pf, pfc, pf_th)
        wf, wfc = field(d, wf, wfc, wf_th)
        print(f"d={d:5.2f} case={case} pf_th={pf_th} | pf={pf} wf={wf}   ", end="\r")
    except socket.timeout:
        pf = wf = False
        print("olcum yok -> alanlar ihlalde                ", end="\r")
    tx.sendto(json.dumps({"pf": pf, "wf": wf}).encode(), ("127.0.0.1", 5006))