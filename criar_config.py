config = """[firebird]
host=192.168.0.198
port=3050
database=C:\\MegaFlex\\DADOS\\MFLEX.FDB
user=SYSDBA
password=masterkey
charset=WIN1252
fbclient=C:\\Program Files (x86)\\Firebird\\Firebird_3_0\\bin\\fbclient.dll

[supabase]
url=https://vfyamghgvabmdimngwev.supabase.co
api_key=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmeWFtZ2hndmFibWRpbW5nd2V2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY1NDM3NTMsImV4cCI6MjA5MjExOTc1M30.n0z94cx-0Wwn7--wfihYiux5UPK0pUnSHLHpqOrLNnM

[sync]
intervalo_minutos=15
log_arquivo=sync_log.txt
ultimo_sync_arquivo=ultimo_sync.json
lote_tamanho=500
retry_tentativas=3
retry_espera_s=5
"""

with open("config.ini", "w", encoding="utf-8") as f:
    f.write(config)

print("config.ini criado com sucesso!")
