
import math
import matplotlib.pyplot as plt

lut = []


# Adjust toe and mid range for more punch
toe_end = 20   # keep toe short to retain blacks
mid_end = 180  # slightly lower mid_end for more mid punch


# Precompute the value at mid_end for a smooth transition
def mid_func(x):
    t = (x - toe_end) / (mid_end - toe_end)
    return (toe_end/255.0) + (t ** 0.7) * ((mid_end - toe_end) / 255.0 * 1.15)

mid_end_val = mid_func(mid_end)

for x in range(256):
    xf = x / 255.0

    if x < toe_end:
        yf = xf ** 1.0
    elif x < mid_end:
        yf = mid_func(x)
        yf = min(yf, 1.0)
    else:
        # Shoulder: start from mid_end_val, end at 1.0
        t = (x - mid_end) / (255 - mid_end)
        y0 = mid_end_val
        y1 = 1.0
        s = t * t * (3 - 2 * t)
        yf = y0 + s * (y1 - y0)
        yf = min(yf, 1.0)

    y = int(round(min(255, max(0, yf * 255))))
    lut.append(y)


# Write output as 4 bytes per line, 64 lines for gamma, then 64 lines for unity gamma
with open("gamma_8bit_rgb_linear_low_mid_pop_smooth.mem", "w") as f:
    # First 64 lines: gamma LUT
    for i in range(64):
        idx = i * 4
        bytes_ = lut[idx:idx+4]
        while len(bytes_) < 4:
            bytes_.append(0)
        line = ''.join(f"{b:02X}" for b in reversed(bytes_))
        f.write(line + "\n")

    # Next 64 lines: unity gamma (linear ramp)
    unity_lut = [int(round(x * 255 / 255)) for x in range(256)]
    for i in range(64):
        idx = i * 4
        bytes_ = unity_lut[idx:idx+4]
        while len(bytes_) < 4:
            bytes_.append(0)
        line = ''.join(f"{b:02X}" for b in reversed(bytes_))
        f.write(line + "\n")

# Plot the gamma curve
plt.figure(figsize=(6,4))
plt.plot(range(256), lut, label="Gamma Curve")
plt.xlabel("Input Value (0-255)")
plt.ylabel("Output Value (0-255)")
plt.title("Gamma Curve: Smooth Toe + Mid Pop")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()
