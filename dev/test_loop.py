# -*- coding: utf-8 -*-
"""Run the real _loop with the LCD/LED stubbed, and exercise every button path.

The page/rendering smoke test missed a real UnboundLocalError inside _loop, so
this covers the loop and the button handlers.
"""
import sys, time, threading, types
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L


def make_app():
    app = L.LCDGlance()
    app.rgb = None                      # engine only exists once the LED connects
    app.lcd = types.SimpleNamespace(
        connected=True, button=lambda b: False, submit=lambda d: None,
        set_bitmap=lambda i: None, update=lambda: None,
        ensure_connected=lambda: None, shutdown=lambda: None)
    app.led = types.SimpleNamespace(set_all=lambda *a, **k: None,
                                    stop_effects=lambda: None, shutdown=lambda: None)
    app.oc.poll = lambda: None
    app.dl.poll = lambda st: None
    return app


print("--- normal loop (3 s) ---", flush=True)
app = make_app()
app.running = True
t = threading.Thread(target=app._loop, daemon=True)
t.start()
time.sleep(3.0)
app.running = False
t.join(timeout=3)
print("   loop ran, thread stopped:", not t.is_alive(), flush=True)

print("--- loop with status + flash overlays (2 s) ---", flush=True)
app2 = make_app()
app2.status_until = time.time() + 1.0
app2.flash_until = time.time() + 0.8
app2.running = True
t2 = threading.Thread(target=app2._loop, daemon=True)
t2.start()
time.sleep(2.0)
app2.running = False
t2.join(timeout=3)
print("   overlays rendered, thread stopped:", not t2.is_alive(), flush=True)

print("--- every button path ---", flush=True)
app3 = make_app()
for name, b in (("B1 prev", L.BTN_1), ("B2 next", L.BTN_2),
                ("B3 status", L.BTN_3), ("B4 flash", L.BTN_4)):
    app3.lcd.button = (lambda bb: (lambda x: x == bb))(b)
    app3.prev_buttons = 0
    app3._btn_ts = 0.0
    before = app3.page
    app3._check_buttons()
    print(f"   {name:12s} page {before}->{app3.page}  "
          f"status={app3.status_until > 0} flash={app3.flash_until > 0}", flush=True)

assert app3.status_until > 0, "B3 did not arm the status readout"
assert app3.flash_until > 0, "B4 did not arm the flash"

print("--- loop survives a raising tick ---", flush=True)
# Raise on the very first control check so the failure is guaranteed to happen,
# then require several further ticks. The window is generous because the first
# tick runs kill_lcd_applets(), which spawns six processes.
app4 = make_app()
calls = {"n": 0}
orig = app4._check_buttons


def boom():
    calls["n"] += 1
    if calls["n"] == 1:
        raise RuntimeError("synthetic tick failure")
    orig()


app4._check_buttons = boom
app4.running = True
t4 = threading.Thread(target=app4._loop, daemon=True)
t4.start()
time.sleep(9.0)
alive = t4.is_alive()
app4.running = False
t4.join(timeout=4)
print(f"   ticks attempted: {calls['n']}   thread alive after failure: {alive}", flush=True)
assert calls["n"] >= 3, f"loop stopped after the raised exception (ticks={calls['n']})"
assert alive, "loop thread died"
print("   -> self-healing loop confirmed", flush=True)

print("\n=== LOOP + BUTTONS TEST PASSED ===")
