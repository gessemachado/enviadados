import configparser
import os
import sys

def _base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def carregar():
    cfg = configparser.ConfigParser()
    path = os.path.join(_base_dir(), 'config.ini')
    if not cfg.read(path, encoding='utf-8'):
        raise FileNotFoundError(f'config.ini não encontrado em: {path}')
    return cfg
