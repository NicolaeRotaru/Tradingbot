#!/usr/bin/env bash
# ============================================================================
# Bootstrap del trading bot SOL su un VPS Ubuntu (DRY-RUN, paper trading).
#
# Da eseguire SUL VPS (come root). Due modi:
#   1) Una botta sola:
#        curl -fsSL https://raw.githubusercontent.com/NicolaeRotaru/Tradingbot/main/scripts/vps-setup.sh | bash
#   2) Oppure dopo aver clonato il repo:
#        bash scripts/vps-setup.sh
#
# Installa Docker, clona/aggiorna il repo, e avvia il bot in dry-run.
# La dashboard FreqUI resta legata a 127.0.0.1 (NON esposta a Internet):
# vi si accede dal proprio PC tramite un tunnel SSH (vedi messaggio finale).
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/NicolaeRotaru/Tradingbot.git"
DIR="${HOME}/Tradingbot"
COMPOSE="docker-compose-sol.yml"

echo "==> 0/4 Prerequisiti (git, curl)..."
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y >/dev/null
  apt-get install -y git curl >/dev/null
fi

echo "==> 1/4 Docker..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
else
  echo "    Docker gia' presente: $(docker --version)"
fi

echo "==> 2/4 Repository..."
if [ -d "${DIR}/.git" ]; then
  git -C "${DIR}" pull --ff-only origin main
else
  git clone "${REPO_URL}" "${DIR}"
fi
cd "${DIR}"

echo "==> 3/4 Permessi user_data (l'utente Docker non e' root) + avvio dry-run..."
# La cartella clonata da root non e' scrivibile dall'utente del container (uid 1000):
# senza questo il bot non riesce a creare il log e va in Restarting. Fix una volta per tutte.
mkdir -p user_data/logs
chown -R 1000:1000 user_data 2>/dev/null || true
docker compose -f "${COMPOSE}" up -d

echo "==> 4/4 Stato dei container:"
docker compose -f "${COMPOSE}" ps

PUBIP="$(curl -fsSL https://api.ipify.org 2>/dev/null || echo 'IP_DEL_TUO_VPS')"
cat <<EOF

============================================================
 OK - Bot avviato in DRY-RUN sul VPS (soldi SIMULATI).
 Resta acceso 24/7 e riparte da solo dopo i riavvii del server.

 Per aprire la dashboard FreqUI in modo SICURO, dal TUO PC (PowerShell):

     ssh -L 8080:127.0.0.1:8080 root@${PUBIP}

 lascia quella finestra aperta, poi nel browser vai su:

     http://127.0.0.1:8080
     utente: freqtrader   password: solbot123

 Comandi utili (sul VPS, dentro ~/Tradingbot):
   log dal vivo:  docker compose -f ${COMPOSE} logs -f
   ferma:         docker compose -f ${COMPOSE} down
   aggiorna:      git pull origin main && docker compose -f ${COMPOSE} up -d
============================================================
EOF
