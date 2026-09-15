import sys, time
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L
L._collect_top()          # prime psutil's per-process cpu sampling
time.sleep(0.6)
print("top procs after filter:")
for p in L._collect_top():
    print(f"   {p.get('name'):28s} cpu={p.get('cpu_percent'):5.1f}%  ram={p.get('memory_percent'):4.1f}%")
L._collect_top(); time.sleep(0.6)
print("\nsecond sample:")
for p in L._collect_top():
    print(f"   {p.get('name'):28s} cpu={p.get('cpu_percent'):5.1f}%")
print("\nidle/system present?", any((p.get('name') or '').lower() in L.SKIP_PROCS for p in L._collect_top()))
