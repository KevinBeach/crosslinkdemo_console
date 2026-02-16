# sRGB gamma curve LUT for RGB888
# 4 bytes per line, 64 lines, unsigned hex
# Each line: RRGGBBAA (AA=0x00)

def srgb_gamma(v):
    v = v / 255.0
    if v <= 0.0031308:
        return int(round(255.0 * 12.92 * v))
    else:
        return int(round(255.0 * (1.055 * (v ** (1.0 / 2.4)) - 0.055)))

lines = []
for i in range(64):
    in_val = int(round(i * 255 / 63))
    out_val = srgb_gamma(in_val)
    # For demonstration, use same value for R, G, B, and 0x00 for A
    line = f"{out_val:02X}{out_val:02X}{out_val:02X}00"
    lines.append(line)

with open("sRGB.mem", "w") as f:
    for line in lines:
        f.write(line + "\n")
