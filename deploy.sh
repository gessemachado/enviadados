#!/bin/bash
# Deploy EnviaDados no VPS HostGator (Ubuntu)
# Execute como root: bash deploy.sh
set -e

# Defina a variável antes de rodar: export PG_PASSWORD="sua_senha"
SENHA_PG="${PG_PASSWORD:?Erro: exporte PG_PASSWORD antes de rodar. Ex: export PG_PASSWORD=suasenha}"
APP_DIR="/opt/enviadados"
WWW_DIR="/var/www/enviadados"

echo "=== 1/7 Instalando dependências ==="
apt-get update -q
apt-get install -y -q postgresql postgresql-contrib python3-pip python3-venv nginx ufw

echo "=== 2/7 Configurando PostgreSQL ==="
systemctl enable postgresql
systemctl start postgresql

# Cria banco e usuário
sudo -u postgres psql -c "CREATE DATABASE enviadados;" 2>/dev/null || echo "Banco já existe"
sudo -u postgres psql -c "CREATE USER enviadados WITH PASSWORD '$SENHA_PG';" 2>/dev/null || echo "Usuário já existe"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE enviadados TO enviadados;"
sudo -u postgres psql -d enviadados -c "GRANT ALL ON SCHEMA public TO enviadados;"

# Cria tabelas
sudo -u postgres psql -d enviadados -f "$APP_DIR/api/schema.sql"

# Permite conexão remota (para o SyncAgent no Windows)
PG_VER=$(psql --version | awk '{print $3}' | cut -d. -f1)
PG_CONF="/etc/postgresql/$PG_VER/main/postgresql.conf"
PG_HBA="/etc/postgresql/$PG_VER/main/pg_hba.conf"

sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"

# Permite o usuário enviadados de qualquer IP (ajuste se quiser restringir)
if ! grep -q "enviadados" "$PG_HBA"; then
    echo "host enviadados enviadados 0.0.0.0/0 scram-sha-256" >> "$PG_HBA"
fi

systemctl restart postgresql

echo "=== 3/7 Configurando API Python ==="
mkdir -p "$APP_DIR"
cp -r /tmp/enviadados-upload/api "$APP_DIR/"

# Senha do banco no config da API
sed -i "s/SENHA_PG_AQUI/$SENHA_PG/" "$APP_DIR/api/config.ini"

python3 -m venv "$APP_DIR/api/venv"
"$APP_DIR/api/venv/bin/pip" install -q -r "$APP_DIR/api/requirements.txt"

echo "=== 4/7 Instalando serviço systemd ==="
cp /tmp/enviadados-upload/enviadados-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable enviadados-api
systemctl start enviadados-api

echo "=== 5/7 Implantando arquivos estáticos ==="
mkdir -p "$WWW_DIR"
cp /tmp/enviadados-upload/*.html "$WWW_DIR/"
cp /tmp/enviadados-upload/auth.js "$WWW_DIR/"
cp -r /tmp/enviadados-upload/mobile "$WWW_DIR/"
chown -R www-data:www-data "$WWW_DIR"

echo "=== 6/7 Configurando Nginx ==="
cp /tmp/enviadados-upload/nginx/enviadados.conf /etc/nginx/sites-available/enviadados
ln -sf /etc/nginx/sites-available/enviadados /etc/nginx/sites-enabled/enviadados
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== 7/7 Firewall ==="
ufw allow 22022/tcp  # SSH (porta atual do VPS)
ufw allow 80/tcp     # HTTP
ufw allow 5432/tcp   # PostgreSQL (para SyncAgent remoto)
ufw --force enable

echo ""
echo "========================================"
echo " Deploy concluído!"
echo " Site:       http://108.174.148.133"
echo " PostgreSQL: porta 5432"
echo "   usuario:  enviadados"
echo "   senha:    $SENHA_PG"
echo ""
echo " Configure o config.ini do SyncAgent:"
echo "   [postgres]"
echo "   host     = 108.174.148.133"
echo "   port     = 5432"
echo "   database = enviadados"
echo "   user     = enviadados"
echo "   password = $SENHA_PG"
echo "========================================"
