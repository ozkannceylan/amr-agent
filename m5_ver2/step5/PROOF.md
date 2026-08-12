# Step 5 — autonomous drive

Every tick here is earned by a live run recorded in this file.

```
[ ] step5.sh deploy then start: world + paint + HMI with sketch up
[ ] Teleop regression: a once, joystick drives, es0/es1/a behave as Step 4
[ ] Auto: select S7, GO -> drives the aisles, arrives within 0.25 m
[ ] Obstacle on route -> HOLD; removed -> resumes; PLC never latched
[ ] es0 mid-drive -> stops; a -> resumes the same route
[ ] Mode to Teleop mid-drive -> goal cancelled, joystick live instantly
[ ] Stale-deploy check: edit ipc/ source, no deploy -> vehicle runs old
    version and start prints the STALE warning
[ ] step5.sh stop -> clean sweep, PLC untouched
```
