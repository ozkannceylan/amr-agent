import socket, threading, time, json
STATE = {"d": 5.0, "v": 0.0}
def stdin_reader():
    print("kullanim: d 3.0  |  v 1.5")
    while True:
        try:
            k, val = input("> ").split(); STATE[k] = float(val)
        except Exception: print("ornek: d 3.0")
threading.Thread(target=stdin_reader, daemon=True).start()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
while True:
    msg = json.dumps(STATE).encode()
    for p in (5005, 5007): s.sendto(msg, ("127.0.0.1", p))
    time.sleep(0.05)