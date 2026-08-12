import socket, json, threading, random
MODE = ["ok"]                       # ok | fa (A donuk) | oa (A ofsetli)
def stdin_reader():
    print("enkoder arizasi: ok | fa | oa")
    while True:
        c = input().strip().lower()
        if c in ("ok", "fa", "oa"): MODE[0] = c
threading.Thread(target=stdin_reader, daemon=True).start()
rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx.bind(("127.0.0.1", 5007)); rx.settimeout(0.3)
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
last_a = 0
while True:
    try:
        v_mm = int(json.loads(rx.recv(128).decode())["v"] * 1000)
        a = v_mm + random.randint(-5, 5)    # bagimsiz kanal gurultusu
        b = v_mm + random.randint(-5, 5)
        if MODE[0] == "fa": a = last_a       # kanal A donmus
        if MODE[0] == "oa": a += 400         # kanal A kaymis
        last_a = a
        tx.sendto(json.dumps({"a": a, "b": b}).encode(), ("127.0.0.1", 5009))
    except socket.timeout:
        pass                                 # dunya sustu -> kopru watchdog'u halleder