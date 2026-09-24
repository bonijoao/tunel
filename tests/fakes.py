import posixpath
import stat as st

import paramiko


class FakeSftp:
    """SFTP em memória. Itens: ("dir",), ("file", bytes) ou ("link", alvo). Caminhos absolutos."""

    def __init__(self):
        self.itens = {"/": ("dir",)}

    # ---- montagem dos cenários dos testes
    def pasta(self, caminho):
        pai = posixpath.dirname(caminho)
        if caminho != "/" and pai not in self.itens:
            self.pasta(pai)
        self.itens.setdefault(caminho, ("dir",))

    def arquivo(self, caminho, conteudo=b""):
        self.pasta(posixpath.dirname(caminho))
        self.itens[caminho] = ("file", conteudo)

    def link(self, caminho, alvo):
        self.pasta(posixpath.dirname(caminho))
        self.itens[caminho] = ("link", alvo)

    def conteudo(self, caminho):
        return self.itens[caminho][1]

    def caminhos(self):
        return sorted(self.itens)

    # ---- API SFTP
    def _attr(self, caminho, seguir):
        item = self.itens.get(caminho)
        if item is None:
            raise FileNotFoundError(caminho)
        if item[0] == "link" and seguir:
            return self._attr(item[1], True)
        a = paramiko.SFTPAttributes()
        a.filename = posixpath.basename(caminho)
        a.st_mtime = 1700000000
        if item[0] == "dir":
            a.st_mode, a.st_size = st.S_IFDIR | 0o755, 0
        elif item[0] == "link":
            a.st_mode, a.st_size = st.S_IFLNK | 0o777, 0
        else:
            a.st_mode, a.st_size = st.S_IFREG | 0o644, len(item[1])
        return a

    def stat(self, caminho):
        return self._attr(caminho, True)

    def lstat(self, caminho):
        return self._attr(caminho, False)

    def listdir_attr(self, caminho):
        if self.itens.get(caminho, (None,))[0] != "dir":
            raise FileNotFoundError(caminho)
        pref = caminho.rstrip("/") + "/"
        nomes = sorted({c[len(pref):].split("/")[0]
                        for c in self.itens if c != caminho and c.startswith(pref)})
        return [self._attr(pref + n, False) for n in nomes]

    def mkdir(self, caminho):
        if caminho in self.itens:
            raise OSError("já existe")
        if self.itens.get(posixpath.dirname(caminho), (None,))[0] != "dir":
            raise FileNotFoundError(posixpath.dirname(caminho))
        self.itens[caminho] = ("dir",)

    def rmdir(self, caminho):
        if any(c != caminho and c.startswith(caminho.rstrip("/") + "/") for c in self.itens):
            raise OSError("pasta não vazia")
        del self.itens[caminho]

    def remove(self, caminho):
        item = self.itens.get(caminho)
        if item is None:
            raise FileNotFoundError(caminho)
        if item[0] == "dir":
            raise OSError("é uma pasta")
        del self.itens[caminho]

    def rename(self, origem, destino):
        if destino in self.itens:
            raise OSError("o destino já existe")
        if self.itens.get(posixpath.dirname(destino), (None,))[0] != "dir":
            raise FileNotFoundError(posixpath.dirname(destino))
        pref = origem.rstrip("/") + "/"
        for c in [c for c in sorted(self.itens) if c == origem or c.startswith(pref)]:
            self.itens[destino + c[len(origem):]] = self.itens.pop(c)

    def put(self, local, remoto, *args, **kwargs):
        if self.itens.get(posixpath.dirname(remoto), (None,))[0] != "dir":
            raise FileNotFoundError(remoto)
        with open(local, "rb") as f:
            self.itens[remoto] = ("file", f.read())

    def get(self, remoto, local, *args, **kwargs):
        item = self.itens.get(remoto)
        if item is None or item[0] != "file":
            raise FileNotFoundError(remoto)
        with open(local, "wb") as f:
            f.write(item[1])
