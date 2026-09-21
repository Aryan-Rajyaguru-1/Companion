# Remote OTA — optional self-hosted relay

**You do not need any of this to use Companion.** It is an opt-in extra for one
specific situation: updating devices that are **not on your LAN**.

| Your situation | What to use | Setup needed |
|---|---|---|
| Device on your desk, USB attached | `companion upload` (serial) | none |
| Device on the same WiFi/LAN | `companion ota upload <ip> --ota-mode local` | none |
| Device on the internet, mobile network, another site | **this directory** | a server + a TLS endpoint |

Everything below is for the third row only. If you never need it, ignore this
directory — the default paths (`--ota-mode local`) keep working exactly as before.

---

## What this sets up

A **relay hub** you host, plus a TLS endpoint in front of it. The hub never
stores firmware; it only pairs one agent with one device and pipes bytes.

```
  your laptop (agent)                your server                 the device
  companion ota upload  ──wss://──►  relay hub  ──ws://──►  ESP32 (RelayDevice)
      --ota-mode remote                :8931                    anywhere
                                          ▲
                                          └─ TLS terminates here
                                             (Cloudflare Tunnel, nginx, Caddy, …)
```

Two properties worth knowing:

- **The hub is transport-agnostic.** Any reverse proxy that terminates TLS and
  forwards WebSockets works — Cloudflare Tunnel is one option, not a requirement.
- **Auth is two-layered.** An agent token gates the agent port, a devices token
  gates the device port, and each board additionally proves a per-device secret.
  A leaked agent token alone cannot flash a device you don't know the secret for.

---

## Quick start

### 1. Generate the hub's shared tokens

Tokens are just high-entropy strings. Keep them out of this repository.

```bash
mkdir -p ~/.companion-relay && chmod 700 ~/.companion-relay
cat > ~/.companion-relay/relay.env <<EOF
COMPANION_RELAY_DEVICES_TOKEN=$(openssl rand -hex 32)
COMPANION_RELAY_AGENTS_TOKEN=$(openssl rand -hex 32)
EOF
chmod 600 ~/.companion-relay/relay.env
```

See `relay.env.example`. The hub also accepts these as plain environment
variables if you'd rather manage them in a container secret store.

### 2. Run the hub

```bash
companion relay hub --listen :8931
```

Sanity check from the same machine:

```bash
curl -s http://127.0.0.1:8931/health                 # {"ok":true}
curl -s "http://127.0.0.1:8931/health?token=$COMPANION_RELAY_AGENTS_TOKEN"
```

To keep it running across reboots, install it as a service — see
`install-relay-hub.sh` and `companion-relay-hub.service.template`.

### 3. Put a TLS endpoint in front of it

Agents and devices connect over **`wss://`**, so the hub must be reachable over
TLS. Pick whichever fits your infrastructure:

- **Cloudflare Tunnel** — no inbound ports, no certificate work:
  `bash setup-tunnel.sh` (supports a quick throwaway URL for testing, or a
  named tunnel for a real hostname).
- **Your own reverse proxy** (nginx/Caddy/Traefik) — no script needed:

  ```caddy
  ota.example.com {
      reverse_proxy 127.0.0.1:8931
  }
  ```

  WebSocket upgrade must be forwarded (`Upgrade`/`Connection` headers for
  nginx; Caddy does this automatically). Companion itself has no opinion about
  the hostname.

### 4. Flash the device firmware

Copy `companion-ide/esp32-bridge-firmware/RelayDevice/config.example.h` to
`config.local.h` (git-ignored) and set your endpoint and identity:

```c
#define WIFI_SSID     "your-ssid"
#define WIFI_PASS     "your-pass"
#define RELAY_HOST    "ota.example.com"   // the TLS endpoint from step 3
#define RELAY_PORT    443
#define RELAY_TLS     true                // wss:// — required through a proxy
#define DEVICE_ID     "esp32-bridge-01"   // unique per board
#define DEVICE_TOKEN  "<COMPANION_RELAY_DEVICES_TOKEN>"
```

Flash it, then open the serial monitor. On first boot the firmware generates a
per-device secret, stores it in NVS, and prints it once:

```
[relay] *** FIRST BOOT: device secret provisioned ***
[relay] *** SECRET: <32 hex chars> ***
```

**Copy that secret now.** It is the board's identity — the hub refuses a push
to a device whose secret doesn't match, which is what stops one compromised
agent from flashing every board on your relay.

### 5. Push

Export the two secrets once per shell — environment variables are preferred,
since flag values are visible in `ps` output and shell history:

```bash
export COMPANION_RELAY_AGENTS_TOKEN=...     # from relay.env
export COMPANION_RELAY_DEVICE_SECRET=...    # the SECRET the board printed

companion relay devices --hub wss://ota.example.com      # is the board online?

companion ota upload esp32-bridge-01 --ota-mode remote \
  --relay-hub wss://ota.example.com \
  ./build/firmware.bin
```

Two other front doors onto the same relay:

```bash
# one device, directly (secret from the env or --device-secret)
companion relay push --hub wss://ota.example.com --device esp32-bridge-01 ./build/firmware.bin

# a whole fleet — secrets come from the local registry, so register once:
companion fleet register esp32-bridge-01 --secret-stdin      # paste the board's SECRET
companion fleet push ./build/firmware.bin --relay-hub wss://ota.example.com
```

Mind the difference: `relay push` and `ota upload --ota-mode remote` take the
secret from `COMPANION_RELAY_DEVICE_SECRET` (or a flag), while `fleet push`
reads it from the registry that `fleet register` populates.

`verify-remote-ota.sh` runs these checks for you end to end.

---

## Customising

| Want to change | How |
|---|---|
| Hub port | `companion relay hub --listen :PORT` (and the unit's `ExecStart` line) |
| Hub hostname | anything — set `RELAY_HOST` in `config.local.h`; no Companion-side config |
| Reverse proxy | nginx/Caddy/Traefik/HAProxy all work; just forward WebSockets |
| TLS termination | at the proxy; the hub itself stays plain `ws://` by design |
| Run as a different user | pass `--user` to `install-relay-hub.sh` |
| Container instead of systemd | install the `companion` binary in the image; `ENTRYPOINT ["companion","relay","hub","--listen",":8931"]` |
| Several devices | one `DEVICE_ID` + secret per board; `fleet` manages the registry |
| Several hubs | independent fleets — devices are identified by id + secret, not by hub |

---

## Security notes

- **Never commit** `relay.env`, device secrets, or a tunnel token. The repo's
  `.gitignore` already excludes `config.local.h`; keep hub secrets in
  `~/.companion-relay/` (mode `600`) or your secret manager.
- **A tunnel token is a credential.** It grants control of that tunnel — treat
  it like an SSH key, and rotate it in your provider's dashboard if it leaks.
- **Prefer `--secret-stdin`** (or `COMPANION_RELAY_DEVICE_SECRET`) over a
  command-line flag, which is visible in `ps` output and shell history.
- **The hub is not a firmware store.** Nothing is persisted server-side; a
  restart only drops current pairings.
- **No password, no OTA.** The relay authenticates the *transport*; if you also
  want ArduinoOTA password checking on the device, configure it in the sketch.

---

## Troubleshooting

| Symptom | Likely cause / check |
|---|---|
| `dial hub agent port: …` fails | proxy not forwarding WebSockets, or wrong scheme (`wss://` needed behind TLS) |
| Device never appears in `relay devices` | device's `DEVICE_TOKEN` ≠ hub's `COMPANION_RELAY_DEVICES_TOKEN`, or a duplicate `DEVICE_ID` (a re-registration supersedes the older socket) |
| Push fails with a secret error | re-read the secret from serial and `fleet register` again |
| Push stalls, then `device stopped ACKing` | device dropped off WiFi; the firmware re-dials automatically — retry |
| Push takes minutes for a 1 MB image | expected: the protocol is stop-and-wait, so throughput ≈ chunk ÷ RTT. LAN is seconds; a long-distance tunnel is minutes |
| Works, then dies after a while | hub or tunnel isn't running as a service — use `install-relay-hub.sh` |

Useful commands:

```bash
journalctl -u companion-relay-hub -f                  # hub log (if installed as a service)
companion relay devices --hub wss://… --token …       # which boards are online
```

---

## Uninstalling

```bash
sudo systemctl disable --now companion-relay-hub
sudo rm /etc/systemd/system/companion-relay-hub.service
sudo systemctl daemon-reload
```

Then remove the tunnel in your provider's dashboard and delete
`~/.companion-relay/`. Devices fall back to `--ota-mode local` on your LAN with
no firmware change.
