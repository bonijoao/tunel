import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from tools import gerar_icone  # noqa: E402


def _placa():
    img = Image.new("RGB", (200, 200), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(100, 10), (190, 100), (100, 190), (10, 100)], fill=(255, 200, 0))
    d.rectangle([90, 90, 110, 110], fill="white")
    return img


def test_fundo_branco_sai_e_branco_interno_fica():
    out = gerar_icone.tornar_fundo_transparente(_placa())
    assert out.getpixel((0, 0))[3] == 0 and out.getpixel((199, 199))[3] == 0
    assert out.getpixel((199, 0))[3] == 0 and out.getpixel((0, 199))[3] == 0
    assert out.getpixel((100, 60))[3] == 255
    assert out.getpixel((100, 100))[3] == 255


def test_gerar_cria_png_e_ico_com_todos_os_tamanhos(tmp_path):
    origem = tmp_path / "logo.jpg"
    _placa().save(origem, quality=95)
    png, ico = gerar_icone.gerar(origem, tmp_path / "saida")
    im = Image.open(png)
    assert im.size == (256, 256) and im.getpixel((0, 0))[3] == 0 and im.getpixel((128, 128))[3] == 255
    tamanhos = Image.open(ico).info["sizes"]
    assert {(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)} <= set(tamanhos)
