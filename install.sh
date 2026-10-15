#!/usr/bin/env bash
# Sets up the family newsletter on the Ubuntu server.
# Run from inside the project folder:  bash install.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(id -un)"
cd "$DIR"

echo "==> Python virtual environment"
sudo apt-get install -y python3-venv >/dev/null
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "==> Web server (nginx in Docker, port 8088)"
mkdir -p site/issues
[ -f site/index.html ] || echo '<!doctype html><meta charset="utf-8"><title>Family Weekly</title><p>No issues yet.</p>' > site/index.html
docker compose up -d

echo "==> systemd service + weekly timer (Sunday 06:00)"
sed -e "s|__DIR__|$DIR|g" -e "s|__USER__|$USER_NAME|g" systemd/newsletter.service \
  | sudo tee /etc/systemd/system/newsletter.service >/dev/null
sudo cp systemd/newsletter.timer /etc/systemd/system/newsletter.timer
sudo systemctl daemon-reload
sudo systemctl enable --now newsletter.timer

IP="$(hostname -I | awk '{print $1}')"
echo
echo "Done."
echo "  Run now:        sudo systemctl start newsletter   (follow: journalctl -u newsletter -f)"
echo "  Next run:       systemctl list-timers newsletter.timer"
echo "  Read it at:     http://$IP:8088"
