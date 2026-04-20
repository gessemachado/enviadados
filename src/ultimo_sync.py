import json
import os
import sys
from datetime import datetime

def _path(nome_arquivo):
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome_arquivo)

def _carregar(nome_arquivo):
    p = _path(nome_arquivo)
    if not os.path.exists(p):
        return {}
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def _salvar(dados, nome_arquivo):
    with open(_path(nome_arquivo), 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, default=str)

def get(tabela, nome_arquivo):
    dados = _carregar(nome_arquivo)
    return dados.get(tabela)

def set(tabela, valor, nome_arquivo):
    dados = _carregar(nome_arquivo)
    dados[tabela] = str(valor) if valor else None
    _salvar(dados, nome_arquivo)
