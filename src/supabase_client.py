import time
import requests
from src import log

def _headers(api_key):
    return {
        'apikey': api_key,
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates',
    }

def upsert(url, api_key, tabela, registros, tentativas=3, espera=5):
    logger = log.get()
    endpoint = f'{url}/rest/v1/{tabela}'
    headers = _headers(api_key)

    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(endpoint, json=registros, headers=headers, timeout=30)
            if resp.status_code in (200, 201):
                return True
            logger.warning(f'{tabela} | tentativa {tentativa} | HTTP {resp.status_code}: {resp.text[:200]}')
        except requests.RequestException as e:
            logger.warning(f'{tabela} | tentativa {tentativa} | erro de rede: {e}')

        if tentativa < tentativas:
            time.sleep(espera * tentativa)

    logger.error(f'{tabela} | falhou após {tentativas} tentativas')
    return False
