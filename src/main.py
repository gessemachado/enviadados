import sys
import time
import src.log as log_mod
import src.config as config_mod
from src.sync import executar_ciclo

def main():
    cfg = config_mod.carregar()
    logger = log_mod.inicializar(cfg['sync'].get('log_arquivo', 'sync_log.txt'))

    agora = '--agora' in sys.argv

    if agora:
        logger.info('Modo --agora: executando ciclo único')
        executar_ciclo(cfg)
        logger.info('Concluído.')
        return

    intervalo = int(cfg['sync'].get('intervalo_minutos', 15)) * 60
    logger.info(f'SyncAgent iniciado — ciclo a cada {intervalo // 60} minutos')

    while True:
        executar_ciclo(cfg)
        logger.info(f'Próximo sync em {intervalo // 60} minutos...')
        time.sleep(intervalo)

if __name__ == '__main__':
    main()
