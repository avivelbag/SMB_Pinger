#!/usr/bin/env bash
# SMB Pinger — VPS Initial Provisioning Script
# Target: DigitalOcean Basic Regular, 1 vCPU / 1 GB RAM, Ubuntu 24.04 LTS
# Run as root: bash setup.sh

set -euo pipefail

DOMAIN="${1:?Usage: setup.sh <domain>}"
APP_USER="smbpinger"
APP_DIR="/opt/smb-pinger"
DATA_DIR="/var/lib/smb-pinger"

echo "==> Installing system packages"
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx sqlite3 ufw fail2ban curl

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:$PATH"

echo "==> Creating service user"
useradd --system --shell /usr/sbin/nologin --home-dir "$APP_DIR" "$APP_USER" || true

echo "==> Creating directories"
mkdir -p "$APP_DIR" "$DATA_DIR/backups"
chown "$APP_USER:$APP_USER" "$DATA_DIR" "$DATA_DIR/backups"

echo "==> Cloning/deploying application"
# Assumes code is already at $APP_DIR (git clone or rsync)
if [ ! -f "$APP_DIR/pyproject.toml" ]; then
    echo "ERROR: Place application code at $APP_DIR first"
    echo "  e.g.: git clone <repo-url> $APP_DIR"
    exit 1
fi

cd "$APP_DIR"
uv sync

echo "==> Setting up .env"
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    # Generate a random admin password
    ADMIN_PASS=$(openssl rand -base64 16)
    ADMIN_HASH=$("$APP_DIR/.venv/bin/python3" -c "import bcrypt; print(bcrypt.hashpw(b'${ADMIN_PASS}', bcrypt.gensalt()).decode())")
    sed -i "s|^SMB_PINGER_ADMIN_PASSWORD_HASH=.*|SMB_PINGER_ADMIN_PASSWORD_HASH=${ADMIN_HASH}|" "$APP_DIR/.env"
    echo "SMB_PINGER_DB_PATH=${DATA_DIR}/smb_pinger.db" >> "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    echo "==> Admin password: $ADMIN_PASS (save this!)"
fi

echo "==> Installing systemd service"
cp "$APP_DIR/deploy/smb-pinger.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable smb-pinger

echo "==> Configuring nginx"
cp "$APP_DIR/deploy/nginx.conf" "/etc/nginx/sites-available/smb-pinger"
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" "/etc/nginx/sites-available/smb-pinger"
ln -sf /etc/nginx/sites-available/smb-pinger /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> Setting up SSL with Let's Encrypt"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" --redirect

echo "==> Configuring firewall"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
echo "y" | ufw enable

echo "==> Setting up backup cron"
cp "$APP_DIR/deploy/backup.sh" /usr/local/bin/smb-pinger-backup
chmod +x /usr/local/bin/smb-pinger-backup
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/smb-pinger-backup") | crontab -

echo "==> Starting application"
systemctl start smb-pinger

echo ""
echo "=== Setup complete ==="
echo "Dashboard: https://$DOMAIN"
echo "Health:    https://$DOMAIN/health"
echo "Admin:     https://$DOMAIN/admin"
echo "Logs:      journalctl -u smb-pinger -f"
