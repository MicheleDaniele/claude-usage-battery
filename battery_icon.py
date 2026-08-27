"""
battery_icon.py — Draws a battery icon filled proportionally to the remaining
percentage, color-coded by level. Used by both the macOS menu bar and the
Windows/Linux system tray.

Rendered at high resolution (super-sampling) then downscaled with anti-aliasing
so edges stay crisp on Retina / HiDPI displays.
"""

import math

from PIL import Image, ImageDraw

from usage_core import level_color

# Super-sampling factor: draw large, then shrink.
SS = 8


def _draw_claude_burst(d, cx, cy, R, color):
    """
    Draw the Claude burst (asterisk/sparkle raycast) centered at (cx, cy)
    with radius R. Used inside the battery to distinguish it from the system
    battery icon. Pass color=(0,0,0,0) to punch a transparent hole (mono mode).
    """
    n = 7                     # 7 lines through center = 14 rays
    inner = R * 0.16          # small gap at the center
    width = max(1, int(R * 0.20))
    for i in range(n):
        ang = math.pi * i / n
        dx, dy = math.cos(ang), math.sin(ang)
        d.line(
            [(cx - dx * R, cy - dy * R), (cx + dx * R, cy + dy * R)],
            fill=color, width=width,
        )
    # Small center dot to tighten the raycast
    d.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=color)


def draw_battery(remaining_pct: int, scale: int = 3, charging: bool = False,
                 mono: bool = False) -> Image.Image:
    """
    Draw a horizontal battery in system-battery style.

    Args:
        remaining_pct: 0..100 — percentage of tokens / charge remaining.
        scale: final icon size multiplier (3 looks sharp on Retina menu bars).
        charging: if True, draws a small lightning bolt overlay.
        mono: True → monochrome (black + alpha) icon for use as a macOS
              "template" image — the OS recolors it automatically for
              light/dark mode, matching the system battery icon behavior.

    Returns:
        A PIL Image in RGBA mode.
    """
    remaining_pct = max(0, min(100, int(remaining_pct)))

    # Dimensions in "units" (scaled later). ~2:1 ratio, not squashed.
    W, H = 26, 13          # battery body
    nub_w, nub_h = 2, 5    # positive terminal nub
    radius = 3             # corner rounding
    wall = 1.4             # wall thickness
    gap = 1.6              # gap between wall and fill

    u = SS                 # 1 unit = SS pixels at draw time
    mx, my = 1.5, 3.0      # transparent margin (my top = battery smaller than
                           # the menu bar height)
    img_w = (W + nub_w) * u
    img_h = H * u
    big = Image.new("RGBA",
                    (int(img_w + 2 * mx * u), int(img_h + 2 * my * u)),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(big)

    ox, oy = mx * u, my * u
    # Template mode uses solid black; macOS recolors it automatically.
    outline = (0, 0, 0, 255) if mono else (170, 170, 170, 255)

    # Outer shell: draw filled rect then punch out the interior to get a
    # clean, uniform wall thickness.
    body = [ox, oy, ox + W * u, oy + H * u]
    d.rounded_rectangle(body, radius=radius * u, fill=outline)
    inner_shell = [
        ox + wall * u, oy + wall * u,
        ox + (W - wall) * u, oy + (H - wall) * u,
    ]
    d.rounded_rectangle(inner_shell, radius=(radius - wall) * u, fill=(0, 0, 0, 0))

    # Positive terminal nub on the right
    ny0 = oy + (H - nub_h) / 2 * u
    d.rounded_rectangle(
        [ox + W * u, ny0, ox + (W + nub_w) * u, ny0 + nub_h * u],
        radius=1 * u, fill=outline,
    )

    # Proportional fill bar
    fx0 = ox + (wall + gap) * u
    fy0 = oy + (wall + gap) * u
    fx1 = ox + (W - wall - gap) * u
    fy1 = oy + (H - wall - gap) * u
    full_w = fx1 - fx0
    fill_w = full_w * remaining_pct / 100

    color = (0, 0, 0, 255) if mono else level_color(remaining_pct)
    if fill_w > 1:
        d.rounded_rectangle(
            [fx0, fy0, fx0 + fill_w, fy1], radius=1.2 * u, fill=color,
        )

    # Claude burst logo, always fully centered and visible:
    # - over the CHARGED region (left of the charge line): punched as a stencil
    #   (transparent hole) so the background shows through;
    # - over the DEPLETED region (right of the charge line): drawn solid.
    # This way the charge line passes through the logo and it stays legible
    # at any percentage.
    cx = ox + (wall + gap) * u + full_w / 2
    cy = oy + H / 2 * u
    R = H * 0.36 * u
    fill_x = fx0 + fill_w

    burst_layer = Image.new("RGBA", big.size, (0, 0, 0, 0))
    _draw_claude_burst(ImageDraw.Draw(burst_layer), cx, cy, R, (0, 0, 0, 255))
    mask = burst_layer.split()[3]  # alpha channel of the burst

    left_mask = mask.copy()   # only where filled (stencil / hole)
    ImageDraw.Draw(left_mask).rectangle([fill_x, 0, big.size[0], big.size[1]], fill=0)
    right_mask = mask.copy()  # only where depleted (solid)
    ImageDraw.Draw(right_mask).rectangle([0, 0, fill_x, big.size[1]], fill=0)

    hole = (0, 0, 0, 0)
    solid = (0, 0, 0, 255) if mono else level_color(remaining_pct)
    big.paste(hole, (0, 0), left_mask)    # stencil over the charged region
    big.paste(solid, (0, 0), right_mask)  # solid over the depleted region

    # Downscale with anti-aliasing to the final size.
    final_w = int((W + nub_w + 2 * mx) * scale)
    final_h = int((H + 2 * my) * scale)
    return big.resize((final_w, final_h), Image.LANCZOS)
