# Gera os ícones da app (icon-192.png, icon-512.png, icon.ico) em frontend/public/icons
# Fundo escuro com uma linha de gráfico a subir em turquesa, nas cores do tema.
# Uso: python scripts/gerar_icones.py [pasta de destino]
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / 'frontend' / 'public'
SCALE = 4   # desenha 4x maior e reduz no fim (contornos suaves)

BACKGROUND = (11, 15, 14, 255)
TEAL = (0, 207, 189, 255)
GLOW = (0, 195, 255, 70)
POINTS = [(0.18, 0.70), (0.38, 0.52), (0.52, 0.62), (0.82, 0.28)]


def polyline(draw, pts, color, width):
    """Linha com cantos e pontas arredondados."""
    draw.line(pts, fill=color, width=round(width), joint='curve')
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def new_icon(size):
    s = size * SCALE
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # quadrado de cantos arredondados
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=s * 0.11, fill=BACKGROUND)

    pts = [(x * s, y * s) for x, y in POINTS]
    # brilho por baixo da linha (camada própria para a transparência se misturar)
    glow = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    polyline(ImageDraw.Draw(glow), pts, GLOW, s * 0.14)
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    polyline(draw, pts, TEAL, s * 0.075)
    # ponto no fim da linha
    d = s * 0.13
    x, y = pts[-1]
    draw.ellipse((x - d / 2, y - d / 2, x + d / 2, y + d / 2), fill=TEAL)
    return img.resize((size, size), Image.LANCZOS)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PUBLIC / 'icons'
    out.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        new_icon(size).save(out / f'icon-{size}.png')
    new_icon(256).save(out / 'icon.ico', sizes=[(256, 256)])   # para atalhos do Windows
    print(f'Ícones gerados em {out}')


if __name__ == '__main__':
    main()
