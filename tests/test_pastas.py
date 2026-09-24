import os
import shutil

from app import ssh


class SftpFalso:
    """SFTP em memória sobre um diretório real (a 'raiz' do PC remoto)."""

    def __init__(self, raiz):
        self.raiz, self.fechado = raiz, False

    def _p(self, caminho):
        return os.path.join(self.raiz, caminho.lstrip("/"))

    def put(self, local, remoto):
        shutil.copyfile(local, self._p(remoto))

    def get(self, remoto, local):
        shutil.copyfile(self._p(remoto), local)

    def mkdir(self, caminho):
        os.mkdir(self._p(caminho))

    def stat(self, caminho):
        return os.stat(self._p(caminho))  # FileNotFoundError (IOError) se não existe

    def listdir_attr(self, caminho):
        class A:
            pass
        saida = []
        for nome in os.listdir(self._p(caminho)):
            a = A()
            a.filename = nome
            a.st_mode = os.lstat(os.path.join(self._p(caminho), nome)).st_mode
            saida.append(a)
        return saida

    def close(self):
        self.fechado = True


class ClienteFalso:
    def __init__(self, sftp):
        self.sftp = sftp

    def open_sftp(self):
        return self.sftp


def _arvore(base):
    (base / "a" / "b").mkdir(parents=True)
    (base / "vazia").mkdir()
    (base / "raiz.txt").write_text("r", encoding="utf-8")
    (base / "a" / "f.txt").write_text("f", encoding="utf-8")
    (base / "a" / "b" / "g.txt").write_text("g", encoding="utf-8")


def _listar(base):
    return sorted(os.path.relpath(os.path.join(d, n), base).replace(os.sep, "/")
                  for d, ds, fs in os.walk(base) for n in ds + fs)


def test_enviar_pasta_recursivo(tmp_path):
    local, remoto = tmp_path / "loc", tmp_path / "rem"
    _arvore(local)
    remoto.mkdir()
    sftp = SftpFalso(str(remoto))
    ssh.enviar_pasta(ClienteFalso(sftp), str(local), "/dest")
    assert _listar(remoto / "dest") == _listar(local)
    assert (remoto / "dest" / "a" / "b" / "g.txt").read_text(encoding="utf-8") == "g"
    assert sftp.fechado


def test_enviar_pasta_em_destino_existente(tmp_path):
    local, remoto = tmp_path / "loc", tmp_path / "rem"
    _arvore(local)
    (remoto / "dest").mkdir(parents=True)
    ssh.enviar_pasta(ClienteFalso(SftpFalso(str(remoto))), str(local), "/dest")
    assert "dest/a/f.txt" in _listar(remoto)


def test_baixar_pasta_recursivo(tmp_path):
    remoto, local = tmp_path / "rem", tmp_path / "loc"
    _arvore(remoto / "origem")
    sftp = SftpFalso(str(remoto))
    ssh.baixar_pasta(ClienteFalso(sftp), "/origem", str(local / "copia"))
    assert _listar(local / "copia") == _listar(remoto / "origem")
    assert (local / "copia" / "vazia").is_dir()
    assert sftp.fechado


def test_pastas_ignoram_links_simbolicos(tmp_path):
    local, remoto = tmp_path / "loc", tmp_path / "rem"
    _arvore(local)
    try:
        os.symlink(local / "raiz.txt", local / "elo.txt")
    except (OSError, NotImplementedError):
        return  # sem permissão para criar links neste sistema
    remoto.mkdir()
    ssh.enviar_pasta(ClienteFalso(SftpFalso(str(remoto))), str(local), "/dest")
    assert "dest/elo.txt" not in _listar(remoto)
    assert "dest/raiz.txt" in _listar(remoto)
