"""
battery_icon.py — Disegna un'icona a forma di batteria riempita in proporzione
alla percentuale rimasta, colorata per livello. Usata sia dal menu bar Mac sia
dalla system tray di Windows.

Disegnata ad alta risoluzione (super-sampling) e poi ridotta con anti-aliasing,
così i bordi restano netti anche sulla barra dei menu retina.
"""

import math

from PIL import Image, ImageDraw

from usage_core import level_color

# Risoluzione di lavoro (super-sampling): disegno grande e poi rimpicciolisco.
SS = 8  # fattore di super-sampling


def _draw_claude_burst(d, cx, cy, R, color):
    """
    Disegna il 'burst' di Claude (raggiera stile asterisco/scintilla) centrato
    in (cx, cy) con raggio R. Usato dentro la batteria per distinguerla da
    quella di sistema. In modalità mono passare color=(0,0,0,0) per bucarlo.
    """
    n = 7                     # 7 linee passanti = 14 raggi
    inner = R * 0.16          # piccolo vuoto centrale
    width = max(1, int(R * 0.20))
    for i in range(n):
        ang = math.pi * i / n
        dx, dy = math.cos(ang), math.sin(ang)
        d.line(
            [(cx - dx * R, cy - dy * R), (cx + dx * R, cy + dy * R)],
            fill=color, width=width,
        )
    # piccolo tondo centrale per compattare la raggiera
    d.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=color)


def draw_battery(remaining_pct: int, scale: int = 3, charging: bool = False,
                 mono: bool = False) -> Image.Image:
    """
    Batteria orizzontale in stile 'stato batteria' del sistema.
    remaining_pct: 0..100 (percentuale di token/carica che resta).
    scale: dimensione finale (3 ~ nitido su barra dei menu retina).
    charging: se True disegna un piccolo fulmine.
    mono: True → icona monocromatica (nero+alpha) da usare come "template"
          nel menu bar macOS: si adatta automaticamente a tema chiaro/scuro,
          esattamente come l'icona della batteria di sistema.
    """
    remaining_pct = max(0, min(100, int(remaining_pct)))

    # Proporzioni in "unità" (poi scalate). Rapporto ~2:1, non schiacciato.
    W, H = 26, 13          # corpo batteria
    nub_w, nub_h = 2, 5    # terminale +
    radius = 3             # raccordo angoli
    wall = 1.4             # spessore parete
    gap = 1.6              # spazio tra parete e riempimento

    u = SS                 # 1 unità = SS pixel in fase di disegno
    mx, my = 1.5, 3.0      # margine trasparente (my alto = batteria più piccola
                           # rispetto all'altezza della barra dei menu)
    img_w = (W + nub_w) * u
    img_h = H * u
    big = Image.new("RGBA",
                    (int(img_w + 2 * mx * u), int(img_h + 2 * my * u)),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(big)

    ox, oy = mx * u, my * u  # margine
    # In modalità template usiamo nero pieno: macOS lo colora da sé.
    outline = (0, 0, 0, 255) if mono else (170, 170, 170, 255)

    # Corpo (guscio esterno) con parete spessa: disegno il rettangolo pieno e
    # poi "svuoto" l'interno per ottenere una parete uniforme e pulita.
    body = [ox, oy, ox + W * u, oy + H * u]
    d.rounded_rectangle(body, radius=radius * u, fill=outline)
    inner_shell = [
        ox + wall * u, oy + wall * u,
        ox + (W - wall) * u, oy + (H - wall) * u,
    ]
    d.rounded_rectangle(inner_shell, radius=(radius - wall) * u, fill=(0, 0, 0, 0))

    # Terminale + a destra
    ny0 = oy + (H - nub_h) / 2 * u
    d.rounded_rectangle(
        [ox + W * u, ny0, ox + (W + nub_w) * u, ny0 + nub_h * u],
        radius=1 * u, fill=outline,
    )

    # Riempimento interno proporzionale
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

    # Logo Claude (burst) centrato e SEMPRE interamente visibile:
    # - sulla parte CARICA (a sinistra della linea di carica) è uno stencil
    #   (foro) che lascia vedere lo sfondo;
    # - sulla parte SCARICA (a destra) è disegnato pieno.
    # Così la "linea di carica" attraversa il logo, che resta leggibile a
    # qualsiasi percentuale.
    cx = ox + (wall + gap) * u + full_w / 2
    cy = oy + H / 2 * u
    R = H * 0.36 * u
    fill_x = fx0 + fill_w

    burst_layer = Image.new("RGBA", big.size, (0, 0, 0, 0))
    _draw_claude_burst(ImageDraw.Draw(burst_layer), cx, cy, R, (0, 0, 0, 255))
    mask = burst_layer.split()[3]  # canale alpha del burst

    left_mask = mask.copy()   # solo dove c'è riempimento (stencil/foro)
    ImageDraw.Draw(left_mask).rectangle([fill_x, 0, big.size[0], big.size[1]], fill=0)
    right_mask = mask.copy()  # solo dove è scarico (pieno)
    ImageDraw.Draw(right_mask).rectangle([0, 0, fill_x, big.size[1]], fill=0)

    hole = (0, 0, 0, 0)                                   # foro trasparente
    solid = (0, 0, 0, 255) if mono else level_color(remaining_pct)
    big.paste(hole, (0, 0), left_mask)                   # stencil sulla carica
    big.paste(solid, (0, 0), right_mask)                 # pieno sulla scarica

    # Riduzione con anti-aliasing alla dimensione finale.
    final_w = int((W + nub_w + 2 * mx) * scale)
    final_h = int((H + 2 * my) * scale)
    return big.resize((final_w, final_h), Image.LANCZOS)
