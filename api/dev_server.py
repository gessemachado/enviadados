"""Servidor de desenvolvimento local — NÃO usado em produção.

Serve os arquivos estáticos (HTML/mobile) e a API Flask no mesmo processo/porta,
replicando o que o nginx faz em produção (ver nginx/enviadados.conf).
"""
import os

from flask import send_from_directory

from app import app

ROOT = os.path.join(os.path.dirname(__file__), '..')


@app.route('/', defaults={'path': 'login.html'})
@app.route('/<path:path>')
def _static(path):
    return send_from_directory(ROOT, path)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)
