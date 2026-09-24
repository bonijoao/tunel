"""Converte o logo (JPEG com fundo branco) em assets/icone.png e assets/icone.ico. Requer Pillow."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

TAMANHOS_ICO = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def tornar_fundo_transparente(img, tolerancia: int = 60):
    """Torna transparente o fundo branco ligado às bordas, sem apagar o branco do interior."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    for canto in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if rgba.getpixel(canto)[3] == 0:
            continue
        ImageDraw.floodfill(rgba, canto, (255, 255, 255, 0), thresh=tolerancia)
    return rgba


def _quadrado(img):
    w, h = img.size
    lado = max(w, h)
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.paste(img, ((lado - w) // 2, (lado - h) // 2), img)
    return tela


def gerar(origem: Path, destino_dir: Path):
    img = tornar_fundo_transparente(Image.open(origem))
    caixa = img.getchannel("A").getbbox()
    if caixa:
        img = img.crop(caixa)
    # redimensiona com alpha pré-multiplicado para não vazar branco do fundo nas bordas
    final = _quadrado(img).convert("RGBa").resize((256, 256), Image.LANCZOS).convert("RGBA")
    destino_dir.mkdir(parents=True, exist_ok=True)
    png, ico = destino_dir / "icone.png", destino_dir / "icone.ico"
    final.save(png)
    final.save(ico, sizes=TAMANHOS_ICO)
    return png, ico


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("origem", nargs="?", default="assets/logo_original.jpg")
    p.add_argument("destino", nargs="?", default="assets")
    a = p.parse_args()
    png, ico = gerar(Path(a.origem), Path(a.destino))
    print(f"Gerado: {png} e {ico}")


if __name__ == "__main__":
    main()
