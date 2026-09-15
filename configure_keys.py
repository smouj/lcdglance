#!/usr/bin/env python3
"""Configure G510 G-keys and backlight in the LGS default profile.

Stops LGS, writes a clean profile with only the macros we need,
assigns G1-G18 across M1/M2/M3, sets backlight colours, restarts LGS,
and verifies persistence.

Layout (M1/M2/M3 = shift states 1/2/3):
    G1–G12  : Unassigned (pass-through) in all modes
    G13     : Terminal WSL | Control UI       | Restart LCDGlance
    G14     : Control UI    | Screenshot       | Unassigned
    G15     : Restart LCDGlance | Unassigned   | Unassigned
    G16     : Screenshot    | Unassigned       | Unassigned
    G17     : Volume Up     | Unassigned       | Unassigned
    G18     : Volume Down   | Unassigned       | Unassigned

Usage:
    python configure_keys.py           # apply changes
    python configure_keys.py --dry-run # preview XML without writing
"""

import os, sys, subprocess, time, uuid, shutil, re

# ── Paths ──────────────────────────────────────────────────────────────
PROFILE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Logitech", "Logitech Gaming Software", "profiles",
)
DEFAULT_PROFILE = os.path.join(PROFILE_DIR, "{09D92D75-3C8C-4723-B06C-4090BCB899C0}.xml")
LGS_EXE = r"C:\Program Files\Logitech Gaming Software\LCore.exe"

# ── Colours per shift state (M1=cyan, M2=white, M3=amber) ─────────────
COLORS = {1: "#00b4d8", 2: "#ffffff", 3: "#ff8c00"}

DRY_RUN = "--dry-run" in sys.argv

# ── Namespace URIs for macro XML ────────────────────────────────────────
NS_NATURAL   = "http://www.logitech.com/Cassandra/2010.1/Macros/Natural"
NS_KEYSTROKE = "http://www.logitech.com/Cassandra/2010.1/Macros/Keystroke"
NS_SHORTCUT  = "http://www.logitech.com/Cassandra/2010.1/Macros/Shortcut"
NS_MEDIA     = "http://www.logitech.com/Cassandra/2010.1/Macros/Media"
NS_MULTIKEY  = "http://www.logitech.com/Cassandra/2010.1/Macros/MultiKey"


def _guid():
    return "{" + str(uuid.uuid4()).upper() + "}"


class MacroBuilder:
    """Accumulates macro definitions and G-key assignments."""

    def __init__(self):
        self.macros = {}       # guid -> (name, hidden, xml_inner)
        self.assignments = {}  # (contextid, shiftstate) -> guid

    # ── Macro types ────────────────────────────────────────────────

    def add_natural(self, name):
        """Unassigned key — passes the G-key through to the OS."""
        g = _guid()
        self.macros[g] = (name, True,
            f'<natural xmlns="{NS_NATURAL}"/>')
        return g

    def add_shortcut(self, name, url, workingdir=""):
        """Launch a program or open a URL."""
        g = _guid()
        wd = f' workingdir="{workingdir}"' if workingdir else ""
        self.macros[g] = (name, False,
            f'<shortcut xmlns="{NS_SHORTCUT}">\n'
            f'          <start url="{url}"{wd}/>\n'
            f'        </shortcut>')
        return g

    def add_media(self, name, task):
        """Media key: volumeup, volumedown, mute, playpause, nexttrack, previoustrack, stop."""
        g = _guid()
        self.macros[g] = (name, False,
            f'<media xmlns="{NS_MEDIA}">\n'
            f'          <do action="{task}"/>\n'
            f'        </media>')
        return g

    def add_multikey(self, name, keys):
        """Multi-key combination.
        keys: list of (value, direction) tuples."""
        g = _guid()
        key_lines = "\n".join(
            f'          <key direction="{d}" value="{v}"/>' for v, d in keys)
        self.macros[g] = (name, False,
            f'<multikey xmlns="{NS_MULTIKEY}">\n{key_lines}\n        </multikey>')
        return g

    # ── Assignment helper ───────────────────────────────────────────

    def assign(self, gkey, shiftstate, guid):
        """Assign guid to G-key at a given shift state."""
        self.assignments[(gkey, shiftstate)] = guid

    # ── XML output ──────────────────────────────────────────────────

    def build_macros_xml(self):
        parts = ["    <macros>"]
        for guid, (name, hidden, inner) in self.macros.items():
            hidden_attr = 'true' if hidden else 'false'
            parts.append(
                f'      <macro name="{name}" color="4278246655" guid="{guid}" hidden="{hidden_attr}">\n'
                f'        {inner}\n'
                f"      </macro>")
        parts.append("    </macros>")
        return "\n".join(parts)

    def build_keyboard_assignments(self):
        lines = ['    <assignments devicecategory="Logitech.Gaming.Keyboard">']
        for (ctx, ss) in sorted(self.assignments.keys(), key=lambda k: (int(k[0][1:]), k[1])):
            guid = self.assignments[(ctx, ss)]
            lines.append(
                f'      <assignment contextid="{ctx}" macroguid="{guid}" '
                f'shiftstate="{ss}" backup="false" original="false"/>')
        lines.append("    </assignments>")
        return "\n".join(lines)


def build_backlight_xml():
    modes = "\n".join(
        f'      <mode color="{COLORS[ss]}" shiftstate="{ss}"/>'
        for ss in sorted(COLORS))
    return (f'    <backlight devicemodel="Logitech.Gaming.Keyboard.G510">\n'
            f'{modes}\n'
            f"    </backlight>")


# ── Build the layout ───────────────────────────────────────────────────

def build_layout():
    """Create the macro builder with all G-key assignments."""
    b = MacroBuilder()

    # G1-G12: unassigned in all modes (natural = pass-through)
    for gn in range(1, 13):
        g = f"G{gn}"
        guid = b.add_natural(g)
        for ss in (1, 2, 3):
            b.assign(g, ss, guid)

    # G13: Terminal WSL | Control UI | Restart LCDGlance
    g13_m1 = b.add_shortcut("Terminal WSL",
        r"C:\Windows\System32\wsl.exe", r"C:\Windows\System32")
    # WSL needs -d Ubuntu-24.4 + bash, but shortcut only takes exe.
    # Use a .bat wrapper that runs: wsl -d Ubuntu-24.04
    g13_m1 = b.add_shortcut("Terminal WSL",
        r"C:\Users\VersusPc\lcdglance\open_wsl.bat")
    g13_m2 = b.add_shortcut("Control UI", r"http://localhost:18789")
    g13_m3 = b.add_shortcut("Restart LCDGlance",
        r"C:\Users\VersusPc\lcdglance\restart.bat")
    b.assign("G13", 1, g13_m1)
    b.assign("G13", 2, g13_m2)
    b.assign("G13", 3, g13_m3)

    # G14: Control UI | Screenshot | Unassigned
    g14_m1 = b.add_shortcut("Control UI", r"http://localhost:18789")
    g14_m2 = b.add_shortcut("Screenshot",
        r"C:\Windows\System32\SnippingTool.exe")
    g14_m3 = b.add_natural("G14")
    b.assign("G14", 1, g14_m1)
    b.assign("G14", 2, g14_m2)
    b.assign("G14", 3, g14_m3)

    # G15: Restart LCDGlance | Unassigned | Unassigned
    g15_m1 = b.add_shortcut("Restart LCDGlance",
        r"C:\Users\VersusPc\lcdglance\restart.bat")
    g15_m2 = b.add_natural("G15")
    g15_m3 = b.add_natural("G15b")
    b.assign("G15", 1, g15_m1)
    b.assign("G15", 2, g15_m2)
    b.assign("G15", 3, g15_m3)

    # G16: Screenshot | Unassigned | Unassigned
    g16_m1 = b.add_shortcut("Screenshot",
        r"C:\Windows\System32\SnippingTool.exe")
    g16_m2 = b.add_natural("G16")
    g16_m3 = b.add_natural("G16b")
    b.assign("G16", 1, g16_m1)
    b.assign("G16", 2, g16_m2)
    b.assign("G16", 3, g16_m3)

    # G17: Volume Up
    g17_m1 = b.add_media("Volume Up", "volumeup")
    g17_m2 = b.add_natural("G17")
    g17_m3 = b.add_natural("G17b")
    b.assign("G17", 1, g17_m1)
    b.assign("G17", 2, g17_m2)
    b.assign("G17", 3, g17_m3)

    # G18: Volume Down
    g18_m1 = b.add_media("Volume Down", "volumedown")
    g18_m2 = b.add_natural("G18")
    g18_m3 = b.add_natural("G18b")
    b.assign("G18", 1, g18_m1)
    b.assign("G18", 2, g18_m2)
    b.assign("G18", 3, g18_m3)

    return b


# ── Profile patching ───────────────────────────────────────────────────

def _replace_block(src, tag, attrs, new_content):
    """Replace <tag attrs...>...</tag> with new_content, using string slicing.

    Avoids re.sub interpretation of backslashes in new_content.
    """
    # Find the opening tag with its attributes
    open_pattern = re.compile(r'<' + tag + r'\b[^>]*' + attrs + r'[^>]*>', re.S)
    m_open = open_pattern.search(src)
    if not m_open:
        raise ValueError(f"Opening <{tag} ...> not found")
    # Find the matching closing tag after the opening
    close_tag = f'</{tag}>'
    close_pos = src.find(close_tag, m_open.end())
    if close_pos < 0:
        raise ValueError(f"Closing </{tag}> not found")
    end = close_pos + len(close_tag)
    return src[:m_open.start()] + new_content + src[end:]


def patch_profile(src, builder):
    """Replace macros, keyboard assignments, and backlight in the profile XML."""
    # 1. Replace <macros>...</macros>
    new_macros = builder.build_macros_xml()
    src = _replace_block(src, 'macros', '', new_macros)

    # 2. Replace Logitech.Gaming.Keyboard assignments
    new_kb = builder.build_keyboard_assignments()
    src = _replace_block(src, 'assignments',
                         r'devicecategory="Logitech\.Gaming\.Keyboard"', new_kb)

    # 3. Replace G510 backlight
    new_bl = build_backlight_xml()
    src = _replace_block(src, 'backlight',
                         r'devicemodel="Logitech\.Gaming\.Keyboard\.G510"', new_bl)

    return src


# ── LGS management ─────────────────────────────────────────────────────

def stop_lgs():
    print("1. Stopping LGS...")
    subprocess.run(["taskkill", "/F", "/IM", "LCore.exe"],
                    capture_output=True, timeout=15)
    time.sleep(2)
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq LCore.exe"],
                       capture_output=True, text=True, timeout=10)
    if "LCore.exe" in r.stdout:
        print("   WARNING: LCore.exe still running!")
        return False
    print("   LGS stopped.")
    return True


def start_lgs():
    print("2. Starting LGS...")
    subprocess.Popen([LGS_EXE], creationflags=0x00000008)
    time.sleep(5)
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq LCore.exe"],
                       capture_output=True, text=True, timeout=10)
    m = re.search(r"LCore\.exe\s+(\d+)", r.stdout)
    pid = m.group(1) if m else "?"
    print(f"   LGS started (PID {pid})")
    return m is not None


def verify(profile_path, builder):
    """Read back the profile and check persistence."""
    src = open(profile_path, encoding="utf-8", errors="replace").read()
    ok = True

    # Check backlight
    bl = re.search(
        r'<backlight devicemodel="Logitech\.Gaming\.Keyboard\.G510"[^>]*>.*?</backlight>',
        src, re.S)
    if bl:
        for ss, color in COLORS.items():
            if f'shiftstate="{ss}"' not in bl.group() or color not in bl.group():
                print(f"   FAILED: backlight shift {ss} color {color}")
                ok = False
    else:
        print("   FAILED: backlight section missing")
        ok = False

    # Check that macro names exist (LGS re-GUIDs on load)
    for guid, (name, hidden, inner) in builder.macros.items():
        # Skip pass-through macros (LGS may rename them)
        if hidden:
            continue
        if f'name="{name}"' not in src:
            # Media macros may have empty name after LGS rewrite
            if '<media' in inner:
                if '<media ' not in src:
                    print(f"   FAILED: media macro missing entirely")
                    ok = False
            else:
                print(f"   FAILED: macro '{name}' not found")
                ok = False

    # Check keyboard assignments for G13-G18
    kb = re.search(
        r'<assignments devicecategory="Logitech\.Gaming\.Keyboard"[^>]*>.*?</assignments>',
        src, re.S)
    if not kb:
        print("   FAILED: keyboard assignments missing")
        return False
    for g in range(13, 19):
        if f'contextid="G{g}"' not in kb.group():
            print(f"   FAILED: G{g} assignment missing")
            ok = False

    # Check G13 specifically has 3 shift states
    g13_count = kb.group().count('contextid="G13"')
    if g13_count < 3:
        print(f"   FAILED: G13 only has {g13_count} shift states (need 3)")
        ok = False

    return ok


# ── Main ───────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(DEFAULT_PROFILE):
        print(f"ERROR: Profile not found: {DEFAULT_PROFILE}")
        sys.exit(1)

    builder = build_layout()

    # Summary
    print("=== G510 G-key configuration ===\n")
    print("Key assignments:")
    for (ctx, ss), guid in sorted(builder.assignments.items(), key=lambda x: (int(x[0][0][1:]), x[0][1])):
        name = builder.macros[guid][0] if guid in builder.macros else "?"
        hidden = builder.macros[guid][1] if guid in builder.macros else False
        label = f"{name}" if not hidden else f"{name} (pass-through)"
        if int(ctx[1:]) >= 13 or ss == 1:
            print(f"  {ctx} M{ss} -> {label}")
    print(f"\nMacros: {len(builder.macros)} total")
    print(f"Backlight: {COLORS}")

    # Read current profile
    src = open(DEFAULT_PROFILE, encoding="utf-8", errors="replace").read()
    patched = patch_profile(src, builder)

    if DRY_RUN:
        out = os.path.join(os.path.dirname(DEFAULT_PROFILE), "lcdglance_profile_patched.xml")
        with open(out, "w", encoding="utf-8") as f:
            f.write(patched)
        print(f"\n[DRY RUN] Patched profile written to:\n  {out}")
        print("No changes applied.")
        return

    # Backup
    backup = DEFAULT_PROFILE + ".lcdglance-backup"
    if not os.path.exists(backup):
        shutil.copy2(DEFAULT_PROFILE, backup)
        print(f"\nBackup: {backup}")

    # Stop LGS
    if not stop_lgs():
        print("Cannot proceed without stopping LGS.")
        sys.exit(1)

    # Write
    print("\n3. Writing profile...")
    with open(DEFAULT_PROFILE, "w", encoding="utf-8") as f:
        f.write(patched)
    print("   Profile written.")

    # Start LGS
    start_lgs()
    time.sleep(8)

    # Verify
    print("\n4. Verification")
    if verify(DEFAULT_PROFILE, builder):
        print("   -> OK, LGS did not revert our changes")
    else:
        print("   -> REVERTED — check manually")

    # Restart LCDGlance
    print("\n5. Restarting LCDGlance...")
    restart_bat = r"C:\Users\VersusPc\lcdglance\restart.bat"
    if os.path.exists(restart_bat):
        subprocess.Popen(["cmd", "/c", restart_bat], creationflags=0x00000008)
        print("   LCDGlance restart triggered")
    else:
        print(f"   WARNING: {restart_bat} not found")

    print("\n=== done ===")


if __name__ == "__main__":
    main()