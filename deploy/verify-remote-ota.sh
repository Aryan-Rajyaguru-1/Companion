#!/usr/bin/env bash
# Verify a remote-OTA relay end to end — OPTIONAL diagnostic.
#
# Checks, in order: hub tokens present → hub answering locally → the public
# TLS endpoint reaching the hub → which boards are online. Optionally pushes an
# image. Each failure prints the likely cause.
#
#   bash verify-remote-ota.sh --hub wss://ota.example.com
#   bash verify-remote-ota.sh --hub wss://ota.example.com --env ~/.companion-relay/relay.env
#   bash verify-remote-ota.sh --hub wss://ota.example.com --push ./build/firmware.bin --device esp32-bridge-01
#
# Tokens come from --env, or from the environment (COMPANION_RELAY_AGENTS_TOKEN
# and COMPANION_RELAY_DEVICE_SECRET).
set -uo pipefail

HUB=""
ENV_FILE=""
DEVICE=""
IMAGE=""
LOCAL_PORT=8931
FAIL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hub)        HUB=$2; shift 2 ;;
    --env)        ENV_FILE=$2; shift 2 ;;
    --device)     DEVICE=$2; shift 2 ;;
    --push)       IMAGE=$2; shift 2 ;;
    --local-port) LOCAL_PORT=$2; shift 2 ;;
    -h|--help)    sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=1; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }
hint() { printf '        → %s\n' "$1"; }

echo "Remote OTA verification"
echo

# ── 1. tokens ──────────────────────────────────────────────────────
echo "1. Credentials"
if [[ -n $ENV_FILE ]]; then
  if [[ -r $ENV_FILE ]]; then
    # shellcheck disable=SC1090
    set -a; . "$ENV_FILE"; set +a
    ok "loaded $ENV_FILE"
  else
    bad "cannot read --env file $ENV_FILE"; hint "check the path and permissions"
  fi
fi
if [[ -n ${COMPANION_RELAY_AGENTS_TOKEN:-} ]]; then
  ok "agent token present"
else
  bad "COMPANION_RELAY_AGENTS_TOKEN is not set"
  hint "export it, or pass --env <relay.env> (see deploy/relay.env.example)"
fi
[[ -n ${COMPANION_RELAY_DEVICE_SECRET:-} ]] \
  && ok "device secret present" \
  || warn "COMPANION_RELAY_DEVICE_SECRET is unset — needed to push (not to list)"
echo

# ── 2. local hub ───────────────────────────────────────────────────
echo "2. Hub on this machine (127.0.0.1:$LOCAL_PORT)"
LOCAL=$(curl -s --max-time 6 "http://127.0.0.1:$LOCAL_PORT/health?token=${COMPANION_RELAY_AGENTS_TOKEN:-}" 2>/dev/null)
if [[ $LOCAL == *'"ok":true'* ]]; then
  ok "hub answered"
  echo "        $(echo "$LOCAL" | head -c 200)"
elif [[ $LOCAL == *'"ok"'* ]]; then
  warn "hub answered but rejected the token — agents token mismatch"
  hint "compare --agents-token with COMPANION_RELAY_AGENTS_TOKEN"
else
  bad "no answer on 127.0.0.1:$LOCAL_PORT"
  hint "start it:  companion relay hub --listen :$LOCAL_PORT"
  hint "or as a service:  sudo bash deploy/install-relay-hub.sh"
fi
echo

# ── 3. public endpoint ─────────────────────────────────────────────
echo "3. Public TLS endpoint"
if [[ -z $HUB ]]; then
  warn "no --hub given — skipping the public-path check"
  hint "e.g. --hub wss://ota.example.com"
else
  case "$HUB" in
    wss://*) BASE="https://${HUB#wss://}" ;;
    ws://*)  BASE="http://${HUB#ws://}" ;;
    http*)   BASE="$HUB" ;;
    *)       BASE="https://$HUB" ;;
  esac
  BASE=${BASE%/}
  PUB=$(curl -s --max-time 15 "$BASE/health?token=${COMPANION_RELAY_AGENTS_TOKEN:-}" 2>/dev/null)
  if [[ $PUB == *'"ok":true'* ]]; then
    ok "$BASE reached the hub"
    echo "        $(echo "$PUB" | head -c 200)"
  else
    bad "$BASE did not reach the hub (got: ${PUB:0:80})"
    hint "proxy not forwarding WebSockets, or TLS/hostname misconfigured"
    hint "check the tunnel/proxy is up, and the route points at :$LOCAL_PORT"
  fi
fi
echo

# ── 4. devices online ──────────────────────────────────────────────
echo "4. Devices online"
if command -v companion >/dev/null 2>&1 && [[ -n $HUB && -n ${COMPANION_RELAY_AGENTS_TOKEN:-} ]]; then
  companion relay devices --hub "$HUB" --token "$COMPANION_RELAY_AGENTS_TOKEN" 2>&1 | sed 's/^/        /' \
    || { bad "could not list devices"; hint "the board may be off, or its DEVICE_TOKEN is wrong"; }
else
  warn "skipped (need the companion CLI on PATH and --hub)"
fi
echo

# ── 5. optional push ───────────────────────────────────────────────
echo "5. Push test"
if [[ -z $IMAGE ]]; then
  warn "skipped — pass --push <image.bin> to exercise a real transfer"
else
  if [[ ! -f $IMAGE ]]; then
    bad "image not found: $IMAGE"
  elif [[ -z $DEVICE ]]; then
    bad "--push needs --device <id>"
  elif [[ -z ${COMPANION_RELAY_DEVICE_SECRET:-} ]]; then
    bad "--push needs COMPANION_RELAY_DEVICE_SECRET (the SECRET from the board's serial log)"
  else
    echo "      transferring $(wc -c < "$IMAGE") bytes to $DEVICE (expect minutes over a tunnel)…"
    if companion ota upload "$DEVICE" --ota-mode remote --relay-hub "$HUB" "$IMAGE"; then
      ok "push completed — the board is rebooting into the new image"
    else
      bad "push failed"
      hint "see deploy/README.md → Troubleshooting for the exact error text"
    fi
  fi
fi
echo

if [[ $FAIL -eq 0 ]]; then
  printf '\033[32mAll checks passed.\033[0m\n'
else
  printf '\033[31mOne or more checks failed\033[0m — see the hints above.\n'
fi
exit $FAIL