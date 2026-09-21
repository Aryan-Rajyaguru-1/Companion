#!/usr/bin/env bash
# Expose the Companion relay hub (default :8931) over TLS — OPTIONAL helper.
#
# Only needed for devices that aren't on your LAN. Nothing else in Companion
# requires this. Cloudflare Tunnel is one convenient option; any reverse proxy
# that terminates TLS and forwards WebSockets works just as well.
#
#   bash setup-tunnel.sh                      # no cloudflared needed: prints proxy recipes
#   bash setup-tunnel.sh --quick              # throwaway https://…trycloudflare.com URL (testing)
#   bash setup-tunnel.sh --token-file F       # named tunnel from a token file
#   sudo bash setup-tunnel.sh --token-file F --install-service
#   sudo bash setup-tunnel.sh --update-unit-token F   # rotate the token in an existing unit
#
# The hub is token-protected, but a quick tunnel is public and short-lived:
# use it to prove the path once, not for anything long-lived.
set -euo pipefail

PORT=8931
MODE=""
TOKEN_FILE=""
TOKEN=""
INSTALL_SERVICE=0
UPDATE_UNIT=0
UNIT=/etc/systemd/system/cloudflared.service

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick)         MODE=quick; shift ;;
    --token)         MODE=named; TOKEN=$2; shift 2 ;;
    --token-file)    MODE=named; TOKEN_FILE=$2; shift 2 ;;
    --port)          PORT=$2; shift 2 ;;
    --install-service) INSTALL_SERVICE=1; shift ;;
    --update-unit-token) UPDATE_UNIT=1; TOKEN_FILE=$2; shift 2 ;;
    -h|--help)       sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

need_cloudflared() {
  if ! command -v cloudflared >/dev/null 2>&1; then
    cat >&2 <<'EOF'
cloudflared is not installed. Either install it —

  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

— or point your own reverse proxy at the hub instead:

  caddy:   ota.example.com { reverse_proxy 127.0.0.1:8931 }
  nginx:   location / { proxy_pass http://127.0.0.1:8931;
                        proxy_http_version 1.1;
                        proxy_set_header Upgrade $http_upgrade;
                        proxy_set_header Connection "upgrade"; }

Then use the resulting wss:// hostname as RELAY_HOST in the firmware config.
EOF
    exit 1
  fi
}

# ── rotate the token inside an already-installed unit ──────────────
# (cloudflared's own `service install` refuses to touch an existing unit, so
# updating the token in place is the supported repair path.)
if [[ $UPDATE_UNIT -eq 1 ]]; then
  [[ $EUID -eq 0 ]] || { echo "run with sudo: sudo bash $0 --update-unit-token FILE" >&2; exit 1; }
  [[ -f $UNIT ]]     || { echo "no unit at $UNIT — nothing to update" >&2; exit 1; }
  [[ -n $TOKEN_FILE && -s $TOKEN_FILE ]] || { echo "pass a non-empty token file" >&2; exit 1; }
  NEW=$(cat "$TOKEN_FILE")
  [[ $NEW =~ ^[A-Za-z0-9_-]+=*$ ]] || { echo "token has unexpected characters — refusing" >&2; exit 1; }
  cp -a "$UNIT" "$UNIT.bak.$(date +%Y%m%d-%H%M%S)"
  sed -i "s|--token [A-Za-z0-9_=-]*|--token $NEW|" "$UNIT"
  systemctl daemon-reload && systemctl restart cloudflared
  echo "» token rotated. Verify with:"
  echo "    journalctl -u cloudflared -n 20 | grep -c 'Registered tunnel connection'   # expect 4"
  echo "    journalctl -u cloudflared -n 20 | grep -c 'Invalid tunnel secret'          # expect 0"
  exit 0
fi

# ── no mode: just document the alternatives ────────────────────────
if [[ -z $MODE ]]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  echo
  echo "Reverse proxy recipes (no Cloudflare):"
  echo "  caddy:  ota.example.com { reverse_proxy 127.0.0.1:$PORT }"
  echo "  nginx:  proxy_pass http://127.0.0.1:$PORT;  + Upgrade/Connection headers"
  echo
  echo "Run with --quick (test) or --token-file (named tunnel) to use Cloudflare."
  exit 0
fi

need_cloudflared

if [[ $MODE == quick ]]; then
  # GOTCHA: without an explicit config, cloudflared may load a local
  # ~/.cloudflared/config.yml whose catch-all rule (commonly http_status:404)
  # silently swallows every request — the tunnel reports "connected" while the
  # edge answers 404 for every path. An explicit single-rule ingress avoids
  # inheriting that.
  TMPCFG=$(mktemp /tmp/companion-ingress.XXXXXX.yml)
  trap 'rm -f "$TMPCFG"' EXIT
  cat > "$TMPCFG" <<EOF
ingress:
  - service: http://localhost:$PORT
EOF
  echo "» starting a quick tunnel to http://localhost:$PORT (Ctrl-C to stop)…"
  echo "» use the printed host as RELAY_HOST, with RELAY_TLS=true RELAY_PORT=443"
  echo
  exec cloudflared tunnel --config "$TMPCFG" --no-autoupdate --url "http://localhost:$PORT"
fi

# ── named tunnel ───────────────────────────────────────────────────
if [[ -n $TOKEN_FILE ]]; then
  [[ -s $TOKEN_FILE ]] || { echo "token file $TOKEN_FILE is missing/empty" >&2; exit 1; }
  TOKEN=$(cat "$TOKEN_FILE")
fi
[[ -n $TOKEN ]] || { echo "no token — pass --token, --token-file, or use --quick" >&2; exit 1; }

if [[ $INSTALL_SERVICE -eq 1 ]]; then
  [[ $EUID -eq 0 ]] || { echo "run with sudo for --install-service" >&2; exit 1; }
  if [[ -f $UNIT ]]; then
    cat >&2 <<EOF
A cloudflared unit already exists at $UNIT.

cloudflared will refuse to overwrite it, and doing so would also discard any
--url/ingress settings it carries for other hostnames on that tunnel. To point
this tunnel at a rotated token, use:

  sudo bash $0 --update-unit-token $TOKEN_FILE

To run a *separate* tunnel for Companion instead, create it in the dashboard and
run it without installing a service:  bash $0 --token-file $TOKEN_FILE
EOF
    exit 1
  fi
  cat > "$UNIT" <<EOF
[Unit]
Description=Cloudflare tunnel for the Companion relay hub
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=$(command -v cloudflared) tunnel run --token $TOKEN
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  chmod 600 "$UNIT"   # a token lives in this file
  systemctl daemon-reload
  systemctl enable --now cloudflared
  sleep 10
  echo "» unit: $(systemctl is-active cloudflared)"
  echo "» registered:   $(journalctl -u cloudflared --no-pager -n 40 2>/dev/null | grep -c 'Registered tunnel connection' || true)   (want 4)"
  echo "» bad secret:   $(journalctl -u cloudflared --no-pager -n 40 2>/dev/null | grep -c 'Invalid tunnel secret' || true)   (want 0)"
  echo
  echo "In the dashboard, point that tunnel's public hostname at http://localhost:$PORT,"
  echo "then set RELAY_HOST to that hostname in the firmware's config.local.h."
  exit 0
fi

echo "» running the tunnel in the foreground (Ctrl-C to stop)…"
exec cloudflared tunnel run --token "$TOKEN"