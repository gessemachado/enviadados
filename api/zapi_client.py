"""Cliente para envio de mensagens de WhatsApp via Z-API (https://developer.z-api.io)."""
import configparser
import os
import re

import requests

_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(os.path.dirname(__file__), 'config.ini'))
_ZAPI = _cfg['zapi'] if _cfg.has_section('zapi') else {}

_TEXT_URL  = 'https://api.z-api.io/instances/{instance_id}/token/{token}/send-text'
_IMAGE_URL = 'https://api.z-api.io/instances/{instance_id}/token/{token}/send-image'


def _formatar_telefone(numero):
    """Remove formatação e garante o DDI 55 (Brasil) no início."""
    digitos = re.sub(r'\D', '', numero or '')
    if not digitos:
        return None
    if not digitos.startswith('55'):
        digitos = '55' + digitos
    return digitos


def numero_destino_padrao():
    return _ZAPI.get('numero_destino', '')


def _headers():
    client_token = _ZAPI.get('client_token', '')
    headers = {'Content-Type': 'application/json'}
    if client_token:
        headers['Client-Token'] = client_token
    return headers


def _post(url_tpl, payload, timeout=15):
    instance_id = _ZAPI.get('instance_id', '')
    token = _ZAPI.get('token', '')
    if not instance_id or not token:
        return False, 'Z-API não configurado (preencha [zapi] instance_id/token em config.ini)'

    try:
        resp = requests.post(
            url_tpl.format(instance_id=instance_id, token=token),
            json=payload,
            headers=_headers(),
            timeout=timeout,
        )
    except requests.RequestException as e:
        return False, str(e)

    if resp.status_code >= 400:
        return False, resp.text

    try:
        return True, resp.json()
    except ValueError:
        return True, resp.text


def enviar_texto(telefone, mensagem):
    """Envia uma mensagem de texto via Z-API.

    Retorna (ok: bool, resultado: dict | str). Em caso de falha, `resultado`
    traz a mensagem de erro.
    """
    numero = _formatar_telefone(telefone)
    if not numero:
        return False, 'Telefone inválido'
    return _post(_TEXT_URL, {'phone': numero, 'message': mensagem})


def enviar_imagem(telefone, imagem_url, legenda=None):
    """Envia uma imagem (por URL pública) via Z-API, com legenda opcional.

    Retorna (ok: bool, resultado: dict | str).
    """
    numero = _formatar_telefone(telefone)
    if not numero:
        return False, 'Telefone inválido'
    if not imagem_url:
        return False, 'URL da imagem obrigatória'

    payload = {'phone': numero, 'image': imagem_url}
    if legenda:
        payload['caption'] = legenda
    return _post(_IMAGE_URL, payload, timeout=20)
