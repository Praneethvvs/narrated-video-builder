"""Screen effects: eased zoom/pan, soft spotlight (dim everything but the control), highlight outline.

All rectangles are in SOURCE pixels (1920x1080 recording) and are drawn before the zoom, so they move with it.
zooms: [{a, b, cx, cy, z}]   spots: [{a, b, x, y, w, h}]   boxes: [{a, b, x, y, w, h, fill?, color?}]
"""
W, H = 1920, 1080
EASE = 0.8          # zoom ease in/out seconds
DIM = (0.07, 0.07, 0.07, 0.07)  # four-step spotlight ramp: total ~25% dim
RAMP = 0.09


def _smooth(x):
    return f"(({x})*({x})*(3-2*({x})))"


def _window(a, b, ease=EASE):
    din = f"clip((it-{a:.3f})/{ease},0,1)"
    dout = f"clip((it-{b - ease:.3f})/{ease},0,1)"
    return f"({_smooth(din)}*(1-{_smooth(dout)}))"


def _box(x, y, w, h, color, t, a, b):
    x, y, w, h = int(max(0, x)), int(max(0, y)), int(max(1, w)), int(max(1, h))
    return f"drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t={t}:enable='between(t,{a:.3f},{b:.3f})'"


def filter_chain(zooms, spots=(), boxes=(), outline="0xF59E0B"):
    parts = []
    for s in spots:
        x, y, w, h, a, b = s["x"], s["y"], s["w"], s["h"], s["a"], s["b"]
        regions = [(0, 0, W, y), (0, y + h, W, H - y - h), (0, y, x, h), (x + w, y, W - x - w, h)]
        for k, op in enumerate(DIM):
            a2, b2 = a + k * RAMP, b - k * RAMP
            for rx, ry, rw, rh in regions:
                if rw > 0 and rh > 0:
                    parts.append(_box(rx, ry, rw, rh, f"black@{op}", "fill", a2, b2))
        parts.append(_box(x - 3, y - 3, w + 6, h + 6, f"{outline}@0.9", "4", a + RAMP, b - RAMP))
    for bx in boxes:
        if bx.get("fill"):
            parts.append(_box(bx["x"], bx["y"], bx["w"], bx["h"], bx.get("color", "0xF7F8FA"), "fill", bx["a"], bx["b"]))
        else:
            parts.append(_box(bx["x"], bx["y"], bx["w"], bx["h"], f"{outline}@0.95", "5", bx["a"], bx["b"]))
    if zooms:
        def expr(base, key):
            return f"{base}" + "".join(f"+{zm[key] - base:.4f}*{_window(zm['a'], zm['b'])}" for zm in zooms)
        z, cx, cy = expr(1.0, "z"), expr(W / 2, "cx"), expr(H / 2, "cy")
        parts.append(f"scale={2 * W}:{2 * H}:flags=lanczos")
        parts.append(f"zoompan=z='{z}':x='clip(2*({cx})-iw/zoom/2,0,iw-iw/zoom)':y='clip(2*({cy})-ih/zoom/2,0,ih-ih/zoom)'"
                     f":d=1:s={W}x{H}:fps=30")
    parts.append("format=yuv420p")
    return ",".join(parts)
