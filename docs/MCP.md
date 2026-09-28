# Companion as an MCP server

`companion mcp` exposes the controller to **any AI agent or program** over the
[Model Context Protocol](https://modelcontextprotocol.io) — Claude Desktop,
Cursor, an IDE assistant, or your own agent loop. The agent gets the same
capabilities you do: check the environment, list boards and ports, compile,
flash a target, and push firmware to a board on the other side of the internet.

## Start it

```bash
companion mcp                                  # read-only tools
companion mcp --hub wss://ota.example.com       # + remote board tools
companion mcp --allow-upload                    # + tools that flash hardware
```

The server speaks JSON-RPC 2.0 over stdin/stdout (the transport desktop MCP
hosts spawn). Diagnostics go to stderr; stdout carries protocol messages only.

## Client configuration

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "companion": {
      "command": "companion",
      "args": ["mcp", "--allow-upload", "--hub", "wss://ota.example.com"]
    }
  }
}
```

**Cursor** — `.cursor/mcp.json` takes the same `command` / `args` shape.

Any other host: spawn the binary, write JSON-RPC lines to its stdin, read them
from stdout.

## Tools

| Tool | What it does | Flashes? |
|---|---|---|
| `companion_doctor` | toolchain, esptool/avrdude/Python, config permissions | no |
| `companion_list_ports` | serial ports and likely board matches | no |
| `companion_board_list` | installed board platforms | no |
| `companion_compile` | compile a sketch, return diagnostics | no |
| `companion_upload` | compile + flash a target through the bridge | **yes** |
| `companion_relay_devices` | boards online on your relay hub | no |
| `companion_relay_push` | push firmware to a board over the internet | **yes** |

Every tool is a thin adapter over the matching CLI command, built fresh per
call, so an agent and a human get identical behaviour — same flags, same errors,
same safety checks. Nothing is reimplemented for the agent's benefit.

## Safety model

- **Flashing is opt-in.** The two tools that write to hardware are refused
  unless the server was started with `--allow-upload`. The refusal is returned
  as a readable tool error, so a model can explain it rather than failing
  mysteriously.
- **Secrets never cross the interface.** The relay tools read
  `COMPANION_RELAY_AGENTS_TOKEN` and `COMPANION_RELAY_DEVICE_SECRET` from the
  environment. No tool schema has a "secret" parameter, so an agent cannot leak
  one by mishandling it.
- **Bounded.** Every call has a timeout, a panic in a tool is reported as a
  tool error rather than killing the server, and one tool runs at a time.
- **Local by default.** The server runs whatever the invoking user can run —
  it is a local process, like the CLI it wraps. Granting an agent access to it
  grants the agent your toolchain and your ability to flash boards.

## Remote boards (anywhere on the internet)

The relay tools work against a self-hosted hub (`deploy/README.md`). Boards run
the `RelayDevice` firmware, which **dials out** to your hub — so no inbound
ports are needed on the board's network, and the agent can push firmware to a
board on another continent from its own machine.

## Notes

- A tool result never contains ANSI colour codes; the text is plain.
- The protocol stream is never polluted by command output — command stdout and
  stderr are captured into the tool result, which is why tool transcripts are
  complete rather than empty.
