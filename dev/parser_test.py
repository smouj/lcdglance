# -*- coding: utf-8 -*-
"""Prove the probe parser raises alerts when an agent/automation finishes."""
import sys, time
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L

OUT1 = """N|1409
T|aaa|cron|succeeded|main|1789430000000|heartbeat-main
T|bbb|subagent|succeeded|main|1789429000000|Old task
C|1789432831
C2|1789164309|rollout.jsonl
"""

OUT2 = """N|1411
T|ccc|cron|failed|dbzlsw|1789431000000|heartbeat-dbzlsw
T|ddd|subagent|succeeded|main|1789430900000|Widget polish
T|aaa|cron|succeeded|main|1789430000000|heartbeat-main
C|1789432831
C2|1789164309|rollout.jsonl
"""

class FakeProc:
    def __init__(self, out):
        self.stdout = out.encode()
        self.stderr = b""

calls = {"n": 0}
def fake_run(*a, **k):
    calls["n"] += 1
    return FakeProc(OUT1 if calls["n"] == 1 else OUT2)

L.subprocess.run = fake_run
m = L.OpenClawMonitor()
m._seen = set()
m._save_seen = lambda: None

m.poll()
s = m.snapshot()
print("poll 1 (baseline):")
print("   alerts   :", s["alerts"])
print("   last_event:", s["last_event"])
print("   ok/fail/total:", s["ok"], s["fail"], s["total"])

m.poll()
s = m.snapshot()
print("\npoll 2 (two new tasks: one cron failure, one subagent success):")
for _, kind, txt in s["alerts"]:
    print(f"   [{kind:4s}] {txt}")
print("   last_event:", s["last_event"])
print("   ok/fail/total:", s["ok"], s["fail"], s["total"])
print("   codex seen/active:", s["codex_seen"], s["codex_active"])

assert s["alerts"], "no alerts raised!"
assert s["last_event"], "no event -> mascot would not react!"
assert s["last_event"]["kind"] == "ok", "last processed event should be the subagent one"
assert "heartbeat-dbzlsw" in [t for _, _, t in s["alerts"]][1], "cron failure missing"
assert any(k == "fail" for _, k, _ in s["alerts"]), "no failure alert"
print("\n=== PARSER OK: alerts fire, mascot event set ===")
