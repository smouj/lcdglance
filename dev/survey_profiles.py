#!/usr/bin/env python3
"""Survey LGS profiles to understand G-key assignment patterns."""
import re, os, sys

PROFDIR = r"C:\Users\VersusPc\AppData\Local\Logitech\Logitech Gaming Software\profiles"

profiles = [f for f in os.listdir(PROFDIR) if f.endswith('.xml') and not f.endswith('.backup')]
print(f"Total profiles: {len(profiles)}")

for pf in sorted(profiles)[:8]:
    fp = os.path.join(PROFDIR, pf)
    src = open(fp, encoding='utf-8', errors='replace').read()
    sz = len(src)
    name_m = re.search(r'name="([^"]*)"', src)
    name = name_m.group(1) if name_m else "?"
    g_assigns = re.findall(r'<assignment[^>]*contextid="G\d+"[^>]*/>', src)
    g_uniq = sorted(set(int(g) for g in re.findall(r'contextid="G(\d+)"', src)))
    mac_count = src.count('<macro ')
    print(f"\n{pf[:55]}  {sz:>7}B  name={name[:30]}")
    print(f"  macros={mac_count}  G-keys={g_uniq[:18]}  G-assigns={len(g_assigns)}")
    
    # Show shiftstates used
    states = sorted(set(int(s) for s in re.findall(r'shiftstate="(\d+)"', src) if int(s) < 10))
    print(f"  shiftstates used: {states}")
    
    # Find macro names that reference G-key assignments
    if g_assigns:
        # Show unique macro GUIDs referenced by G-keys
        guids = set()
        for a in g_assigns:
            gm = re.search(r'macroguid="([^"]*)"', a)
            if gm:
                guids.add(gm.group(1))
        # Find their names
        for g in list(guids)[:5]:
            nm = re.search(rf'macro\b[^>]*guid="{re.escape(g)}"[^>]*name="([^"]*)"', src)
            print(f"  guid={g[:8]}... -> name={nm.group(1) if nm else '?'}")

# Deep dive on the default profile
print("\n\n=== DEFAULT PROFILE DEEP DIVE ===")
dp = os.path.join(PROFDIR, "{09D92D75-3C8C-4723-B06C-4090BCB899C0}.xml")
src = open(dp, encoding='utf-8', errors='replace').read()

# What shiftstates exist for G-keys?
kb_sec = re.search(r'<assignments devicecategory="Logitech\.Gaming\.Keyboard"[^>]*>(.*?)</assignments>', src, re.S)
if kb_sec:
    states = sorted(set(int(s) for s in re.findall(r'shiftstate="(\d+)"', kb_sec.group(1))))
    print(f"Keyboard shiftstates: {states}")
    # Show G1 assignment across all states
    for a in re.findall(r'<assignment[^>]*contextid="G1"[^>]*/>', kb_sec.group(1)):
        gm = re.search(r'macroguid="([^"]*)"', a)
        ss = re.search(r'shiftstate="(\d+)"', a)
        guid = gm.group(1) if gm else "?"
        # Find macro name
        nm = re.search(rf'macro\b[^>]*guid="{re.escape(guid)}"[^>]*name="([^"]*)"', src)
        print(f"  G1 shift={ss.group(1) if ss else '?'} -> guid={guid[:12]}... name={nm.group(1) if nm else '?'}")

# What device categories have assignments for the G510?
for cat in re.findall(r'<assignments devicecategory="([^"]*)"', src):
    sec = re.search(rf'<assignments devicecategory="{re.escape(cat)}"[^>]*>.*?</assignments>', src, re.S)
    if sec:
        ctxs = sorted(set(re.findall(r'contextid="([^"]*)"', sec.group(1))))
        n_assigns = sec.group(1).count('<assignment')
        print(f"\n{cat}: {n_assigns} assignments, keys={ctxs[:20]}")