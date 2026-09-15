# -*- coding: utf-8 -*-
"""Can a 9-10 px bold body coexist with an 11 px title bar?"""
import sys, os
sys.path.insert(0, r"C:\Users\VersusPc\lcdglance")
import lcdglance as L
from PIL import Image, ImageDraw, ImageFont

F = r"C:\Windows\Fonts\consolab.ttf"
# layout under test: 11 px title at y=0, rule at y=12, three 9-10 px rows
TITLE = "SYSTEM"
SAMPLES = ["CPU  37.4%", "RAM  62.1%", "DSK  71.3%"]
CANDS = [("a_9_t120", 9, 120), ("b_9_t135", 9, 135),
         ("c_10_t120", 10, 120), ("d_10_t135", 10, 135)]
out = r"C:\Users\VersusPc\lcdglance\preview"
os.makedirs(out, exist_ok=True)
rows = []
for name, size, thr in CANDS:
    img = Image.new("L", (L.W, L.H), 0)
    d = ImageDraw.Draw(img)
    t = ImageFont.truetype(F, 11)
    b = ImageFont.truetype(F, size)
    d.text((2, -1), TITLE, font=t, fill=255)
    d.line([(0, 12), (159, 12)], fill=255)
    y = 13
    for s in SAMPLES:
        d.text((3, y), s, font=b, fill=255)
        y += 10.5 if size <= 9 else 10.6
    L.BIN_THRESHOLD = thr
    back = L.mono_to_image(L.to_mono_bytes(img))
    rows.append((name, back.resize((L.W * 8, L.H * 8), Image.NEAREST)))
    print(name, "size", size, "thr", thr, flush=True)
sheet = Image.new("RGB", (rows[0][1].width, sum(r.height + 10 for _, r in rows)), (40, 40, 40))
y = 0
for _, r in rows:
    sheet.paste(r.convert("RGB"), (0, y)); y += r.height + 10
sheet.save(os.path.join(out, "_small.png"))
print("order:", ",".join(n for n, _ in rows))
