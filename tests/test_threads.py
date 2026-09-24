import ast
from pathlib import Path

ARQUIVOS = ["app/ui/janela.py", "app/ui/ferramentas.py"]
PROIBIDOS_ZERO_ARGS = {"get"}                       # StringVar.get() / Combobox.get()
PROIBIDOS = {"selecionados", "caminho_atual", "perfil", "senha", "perfil_valido", "winfo_children"}


def _tarefas(arvore):
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == "tarefa":
            yield no


def test_nenhuma_tarefa_le_tk():
    total = 0
    for arq in ARQUIVOS:
        arvore = ast.parse(Path(arq).read_text(encoding="utf-8"))
        for tarefa in _tarefas(arvore):
            total += 1
            for no in ast.walk(tarefa):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                    nome = no.func.attr
                    assert not (nome in PROIBIDOS_ZERO_ARGS and not no.args and not no.keywords), \
                        f"{arq}:{no.lineno} {nome}() dentro de tarefa"
                    assert nome not in PROIBIDOS, f"{arq}:{no.lineno} {nome}() dentro de tarefa"
    assert total >= 8   # a convenção está sendo usada (janela + ferramentas)
