# -*- coding: utf-8 -*-
"""Ask the Logitech LED SDK what devices it can actually drive.

LogiLedInit() succeeds even with zero supported devices, so device.count is the
number that matters: if it is 0, every SetLighting call is a no-op on hardware.
"""
import ctypes, os

dll = r"C:\Program Files\Logitech Gaming Software\SDK\LED\x64\LogitechLed.dll"
if not os.path.exists(dll):
    print("LED SDK dll not found:", dll)
    raise SystemExit(1)

led = ctypes.WinDLL(dll)
led.LogiLedGetConfigOptionNumber.argtypes = [ctypes.c_wchar_p,
                                             ctypes.POINTER(ctypes.c_double)]
led.LogiLedGetConfigOptionString.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                                             ctypes.c_int]
led.LogiLedGetConfigOptionString.restype = ctypes.c_bool

print("LogiLedInit() ->", bool(led.LogiLedInit()))

d = ctypes.c_double(-1.0)
ok = led.LogiLedGetConfigOptionNumber("device.count", ctypes.byref(d))
print(f"device.count (ok={ok}) -> {d.value}")

count = int(d.value or 0)
for i in range(1, count + 1):
    buf = ctypes.create_unicode_buffer(256)
    led.LogiLedGetConfigOptionString(f"device.{i}.name", buf, 256)
    t = ctypes.c_double(0.0)
    led.LogiLedGetConfigOptionNumber(f"device.{i}.type", ctypes.byref(t))
    print(f"  device {i}: name={buf.value!r} type={t.value}")

# does a colour call report success?
for scope, name in ((0, "LOGI_LED_BITMAP 0x00000001"), (0x00000001, "keyboard bit"),
                    (0x00000002, "logo bit"), (0x00000004, "primary bit")):
    r = led.LogiLedSetLightingForTargetZone(scope, 0, 100, 0, 0) \
        if hasattr(led, "LogiLedSetLightingForTargetZone") else None
print("SetLighting(red) returned", led.LogiLedSetLighting(100, 0, 0))
print("RestoreLighting ->", led.LogiLedRestoreLighting())
led.LogiLedShutdown()
