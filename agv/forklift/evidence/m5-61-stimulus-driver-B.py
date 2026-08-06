#!/usr/bin/env python3
"""m5-61 second stimulus: one more warning pair, then the link-loss form."""
import re, subprocess, sys, time
from datetime import datetime, timezone
WORLD="forklift_arena"; NAME="intruder"; TOL=0.02; EID=130
def stamp():
    n=datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%S.")+"{:03d}Z".format(n.microsecond//1000)
def say(c,d): print("{} | {} | {}".format(stamp(),c,d),flush=True)
def run(a,t=15): return subprocess.run(a,capture_output=True,text=True,timeout=t)
def read_pose():
    r=run(["gz","model","-m",NAME,"-p"])
    m=re.search(r"\[(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\]",r.stdout)
    if not m: say("ABORT","no pose read back: "+r.stdout.strip()[:200]); sys.exit(2)
    return float(m.group(1)),float(m.group(2)),float(m.group(3))
def move(x,y,label):
    req=("name: \x27{}\x27 id: {} position: {{ x: {} y: {} z: 0.3 }} "
         "orientation: {{ w: 1 }}").format(NAME,EID,x,y)
    t0=stamp()
    r=run(["gz","service","-s","/world/{}/set_pose".format(WORLD),
           "--reqtype","gz.msgs.Pose","--reptype","gz.msgs.Boolean",
           "--timeout","5000","--req",req])
    say("STIMULUS","{}: issued {} -> ({}, {}) returned {}".format(
        label,t0,x,y,r.stdout.strip().replace("\n"," ")))
    time.sleep(0.5); px,py,pz=read_pose()
    if abs(px-x)>TOL or abs(py-y)>TOL:
        say("ABORT","read-back ({:.3f},{:.3f}) != ({},{}); run DISCARDED".format(px,py,x,y)); sys.exit(3)
    say("READBACK","{}: ({:.3f}, {:.3f}, {:.3f})".format(label,px,py,pz))
say("START","m5-61 stimulus 2")
for x,y,label,hold in [
    (10.0,4.0,"W4 WARNING ONLY (fourth intrusion)",9),
    (11.6,4.0,"C5 CONTROL B - in the corridor, 0.24 m outside the boundary",12),
]:
    move(x,y,label); say("HOLD","{}: holding {} s".format(label,hold)); time.sleep(hold)
say("EXIT","stimulus 2 complete")
