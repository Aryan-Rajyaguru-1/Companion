#!/usr/bin/env bash
# Install the Companion relay hub as a systemd service (optional).
#
# Run this only if you want devices reachable from outside your LAN — see
# deploy/README.md. It generates the hub's tokens if you don't have them yet,
# renders companion-relay-hub.service.template, enables the unit and verifies
# that the hub answers locally.
#
#   sudo bash install-relay-hub.sh [options]
#
#   --user NAME     run the hub as this user   (default: the sudo caller)
#   --bin PATH      companion binary           (default: `command -v companion`)
#   --env FILE      token file                 (default: <user home>/.companion-relay/relay.env)
#   --port N        listen port                (default: 8931)
#   --workdir DIR   service working directory  (default: the user's home)
#   --force         overwrite an existing unit (a .bak copy is always kept)
set -euo pipefail

PORT=8931
TARGET_USER=${SUDO_USER:-$(id -un)}
BIN=${COMPANION_BIN:-}
ENV_FILE=
WORKDIR=
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)    TARGET_USER=$2; shift 2 ;;
    --bin)     BIN=$2; shift 2 ;;
    --env)     ENV_FILE=$2; shift 2 ;;
    --port)    PORT=$2; shift 2 ;;
    --workdir) WORKDIR=$2; shift 2 ;;
    --force)   FORCE=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "run this with sudo: sudo bash $0 $*" >&2
  exit 1
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
if [[ -z $TARGET_HOME || ! -d $TARGET_HOME ]]; then
  echo "cannot resolve home directory for user $TARGET_USER" >&2
  exit 1
fi
TARGET_GROUP=$(id -gn "$TARGET_USER")
[[ -n $BIN ]]        || BIN=$(command -v companion || true)
[[ -n $ENV_FILE ]]   || ENV_FILE="$TARGET_HOME/.companion-relay/relay.env"
[[ -n $WORKDIR ]]    || WORKDIR=$TARGET_HOME

if [[ -z $BIN || ! -x $BIN ]]; then
  echo "companion binary not found — pass --bin /path/to/companion" >&2
  echo "(build it with: go build -o companion .  inside companion-cli/)" >&2
  exit 1
fi

TEMPLATE=$(dirname "$(readlink -f "$0")")/companion-relay-hub.service.template
if [[ ! -f $TEMPLATE ]]; then
  echo "missing $TEMPLATE — run this script from the deploy/ directory" >&2
  exit 1
fi

# ── tokens ─────────────────────────────────────────────────────────
if [[ ! -f $ENV_FILE ]]; then
  echo "» no token file at $ENV_FILE — generating one"
  mkdir -p "$(dirname "$ENV_FILE")"
  chmod 700 "$(dirname "$ENV_FILE")"
  DEV=${COMPANION_RELAY_DEVICES_TOKEN:-$(openssl rand -hex 32)}
  AGT=${COMPANION_RELAY_AGENTS_TOKEN:-$(openssl rand -hex 32)}
  umask 077
  cat > "$ENV_FILE" <<EOF
COMPANION_RELAY_DEVICES_TOKEN=$DEV
COMPANION_RELAY_AGENTS_TOKEN=$AGT
EOF
  chown "$TARGET_USER:$TARGET_GROUP" "$ENV_FILE" 2>/dev/null || true
  chmod 600 "$ENV_FILE"
  echo
  echo "  ┌─ put this in the board's config.local.h ─────────────────────"
  echo "  │  #define DEVICE_TOKEN  \"$DEV\""
  echo "  └──────────────────────────────────────────────────────────────"
  echo "  Agent token (keep secret, never commit):"
  echo "    $AGT"
  echo
else
  chmod 600 "$ENV_FILE"
  echo "» using existing token file $ENV_FILE"
  if grep -q 'replace-with-openssl' "$ENV_FILE"; then
    echo "  WARNING: the file still contains the template placeholders —" >&2
    echo "           replace them with: openssl rand -hex 32" >&2
  fi
fi
for key in COMPANION_RELAY_DEVICES_TOKEN COMPANION_RELAY_AGENTS_TOKEN; do
  grep -q "^$key=" "$ENV_FILE" || { echo "$ENV_FILE is missing $key" >&2; exit 1; }
done

# ── unit ───────────────────────────────────────────────────────────
UNIT=/etc/systemd/system/companion-relay-hub.service
if [[ -f $UNIT && $FORCE -ne 1 ]]; then
  BAK="$UNIT.bak.$(date +%Y%m%d-%H%M%S)"
  cp -a "$UNIT" "$BAK"
  echo "» existing unit backed up to $BAK"
fi

sed -e "s|@USER@|$TARGET_USER|g" \
    -e "s|@GROUP@|$TARGET_GROUP|g" \
    -e "s|@BIN@|$BIN|g" \
    -e "s|@WORKDIR@|$WORKDIR|g" \
    -e "s|@ENVFILE@|$ENV_FILE|g" \
    -e "s|@PORT@|$PORT|g" \
    "$TEMPLATE" > "$UNIT"
echo "» wrote $UNIT (user=$TARGET_USER port=$PORT)"

systemctl daemon-reload
systemctl enable --now companion-relay-hub.service
sleep 5

if ! systemctl is-active --quiet companion-relay-hub.service; then
  echo "» hub failed to start — last log lines:" >&2
  journalctl -u companion-relay-hub --no-pager -n 20 >&2 || true
  exit 1
fi
echo "» unit active: $(systemctl is-active companion-relay-hub.service)"

AGT=$(grep -E '^COMPANION_RELAY_AGENTS_TOKEN=' "$ENV_FILE" | cut -d= -f2-)
echo "» local /health:"
curl -s --max-time 8 "http://127.0.0.1:$PORT/health?token=$AGT" || echo "  (no answer)"
echo
echo "Next steps:"
echo "  1. expose :$PORT over TLS and note the wss:// hostname (see setup-tunnel.sh),"
echo "     then set RELAY_HOST / RELAY_TLS=true in the board's config.local.h"
echo "  2. flash a board and register it:  companion relay devices --hub wss://<host>"
echo
echo "Logs:     journalctl -u companion-relay-hub -f"
echo "Rollback: systemctl disable --now companion-relay-hub && rm $UNIT && systemctl daemon-reload"