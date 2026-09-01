#!/bin/bash
# Script que roda no VPS a cada push no GitHub.
# Localização esperada: /opt/deploy-enviadados.sh
set -e

REPO_DIR="/opt/enviadados-repo"
WWW_DIR="/var/www/enviadados"
APP_DIR="/opt/enviadados"

echo "=== Deploy iniciado: $(date) ==="

# 1. Atualiza o repositório
cd "$REPO_DIR"
git pull origin master

# 2. Atualiza arquivos estáticos (HTML, JS, mobile)
cp -f *.html "$WWW_DIR/"
cp -f auth.js "$WWW_DIR/"
cp -rf mobile "$WWW_DIR/"

# Garante pasta de mídia (uploads de templates WhatsApp)
mkdir -p "$WWW_DIR/media"
chown -R www-data:www-data "$WWW_DIR"

# 3. Atualiza código da API (sem sobrescrever config.ini com a senha real)
cp -f api/app.py         "$APP_DIR/api/app.py"
cp -f api/zapi_client.py "$APP_DIR/api/zapi_client.py"
cp -f api/requirements.txt "$APP_DIR/api/requirements.txt"
cp -f api/schema.sql  "$APP_DIR/api/schema.sql"

# 4. Instala dependências novas (se houver)
"$APP_DIR/api/venv/bin/pip" install -q -r "$APP_DIR/api/requirements.txt"

# 5. Reinicia o serviço Flask
systemctl restart enviadados-api

echo "=== Deploy concluido: $(date) ==="
