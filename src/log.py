import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

_logger = None

def _base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def inicializar(nome_arquivo='sync_log.txt'):
    global _logger
    if _logger:
        return _logger

    path = os.path.join(_base_dir(), nome_arquivo)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')

    handler_arquivo = TimedRotatingFileHandler(
        path, when='midnight', backupCount=30, encoding='utf-8'
    )
    handler_arquivo.setFormatter(fmt)

    handler_console = logging.StreamHandler(sys.stdout)
    handler_console.setFormatter(fmt)

    _logger = logging.getLogger('syncagent')
    _logger.setLevel(logging.INFO)
    _logger.addHandler(handler_arquivo)
    _logger.addHandler(handler_console)
    return _logger

def get():
    return _logger or inicializar()
