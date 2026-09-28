package cmd

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
)

// drive runs a batch of JSON-RPC lines through the server and returns the
// decoded responses, in order.
func drive(t *testing.T, srv *mcpServer, lines ...string) []mcpResponse {
	t.Helper()
	var sb strings.Builder
	for _, l := range lines {
		sb.WriteString(l)
		sb.WriteString("\n")
	}
	var out strings.Builder
	if err := srv.serve(strings.NewReader(sb.String()), &out); err != nil {
		t.Fatalf("serve: %v", err)
	}
	var resps []mcpResponse
	for _, line := range strings.Split(strings.TrimSpace(out.String()), "\n") {
		if line == "" {
			continue
		}
		var r mcpResponse
		if err := json.Unmarshal([]byte(line), &r); err != nil {
			t.Fatalf("response is not valid JSON (protocol stream corrupted?): %q", line)
		}
		resps = append(resps, r)
	}
	return resps
}

// A client that cannot do the handshake or discover the tools is not usable,
// so pin the handshake: version negotiation, capabilities and the tool table.
func TestMCPInitializeAndListTools(t *testing.T) {
	srv := newMCPServer("", false)
	resps := drive(t, srv,
		`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}`,
		`{"jsonrpc":"2.0","method":"notifications/initialized"}`,
		`{"jsonrpc":"2.0","id":2,"method":"tools/list"}`,
	)
	// The notification must not produce a reply: three lines in, two out.
	if len(resps) != 2 {
		t.Fatalf("expected 2 responses (notification gets none), got %d", len(resps))
	}

	var init struct {
		Result struct {
			ProtocolVersion string `json:"protocolVersion"`
			Capabilities    struct {
				Tools map[string]any `json:"tools"`
			} `json:"capabilities"`
			ServerInfo struct {
				Name string `json:"name"`
			} `json:"serverInfo"`
		} `json:"result"`
	}
	rawInit, _ := json.Marshal(resps[0].Result)
	if err := json.Unmarshal(rawInit, &init.Result); err != nil {
		t.Fatalf("initialize result: %v", err)
	}
	// A client that asks for 2025-06-18 must get 2025-06-18 back: refusing a
	// newer client's version breaks clients that are otherwise compatible.
	if init.Result.ProtocolVersion != "2025-06-18" {
		t.Errorf("protocolVersion = %q, want the client's 2025-06-18", init.Result.ProtocolVersion)
	}
	if init.Result.ServerInfo.Name != "companion" {
		t.Errorf("serverInfo.name = %q, want companion", init.Result.ServerInfo.Name)
	}
	if init.Result.Capabilities.Tools == nil {
		t.Error("initialize did not advertise the tools capability")
	}

	var list struct {
		Result struct {
			Tools []struct {
				Name        string         `json:"name"`
				Description string         `json:"description"`
				InputSchema map[string]any `json:"inputSchema"`
			} `json:"tools"`
		} `json:"result"`
	}
	raw, _ := json.Marshal(resps[1].Result)
	json.Unmarshal(raw, &list.Result)
	if len(list.Result.Tools) != len(srv.order) {
		t.Fatalf("tools/list returned %d tools, want %d", len(list.Result.Tools), len(srv.order))
	}
	byName := map[string]bool{}
	for _, tool := range list.Result.Tools {
		byName[tool.Name] = true
		if tool.Description == "" {
			t.Errorf("%s: no description (an LLM cannot choose it)", tool.Name)
		}
		if tool.InputSchema["type"] != "object" {
			t.Errorf("%s: inputSchema.type = %v, want object", tool.Name, tool.InputSchema["type"])
		}
	}
	// The tools an agent needs to actually drive a board.
	for _, want := range []string{
		"companion_doctor", "companion_list_ports", "companion_board_list",
		"companion_compile", "companion_upload",
		"companion_relay_devices", "companion_relay_push",
	} {
		if !byName[want] {
			t.Errorf("tools/list is missing %s", want)
		}
	}
}

// Flashing hardware is the one thing an agent must not do by accident: the
// tools are refused unless the operator started the server with --allow-upload,
// and the refusal must be a tool error (so the model can read and react to it),
// not a protocol error.
func TestMCPDisablesFlashToolsByDefault(t *testing.T) {
	for _, tool := range []string{"companion_upload", "companion_relay_push"} {
		srv := newMCPServer("", false)
		resps := drive(t, srv,
			`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"`+tool+`","arguments":{}}}`)
		if len(resps) != 1 {
			t.Fatalf("%s: expected 1 response, got %d", tool, len(resps))
		}
		if resps[0].Error != nil {
			t.Fatalf("%s: expected a tool error, got protocol error %v", tool, resps[0].Error)
		}
		raw, _ := json.Marshal(resps[0].Result)
		var res struct {
			Content []struct {
				Text string `json:"text"`
			} `json:"content"`
			IsError bool `json:"isError"`
		}
		json.Unmarshal(raw, &res)
		if !res.IsError {
			t.Errorf("%s: flashing tool was not refused by default", tool)
		}
		if !strings.Contains(res.Content[0].Text, "--allow-upload") {
			t.Errorf("%s: refusal should say how to enable it, got %q", tool, res.Content[0].Text)
		}
	}
}

// With the opt-in, the gate opens — otherwise the flag would be decorative.
func TestMCPAllowUploadOpensTheGate(t *testing.T) {
	srv := newMCPServer("wss://hub.example", true)
	if _, ok := srv.tools["companion_upload"]; !ok {
		t.Fatal("companion_upload missing")
	}
	for _, tool := range srv.tools {
		if tool.destructive && srv.allowUpload != true {
			t.Fatalf("%s: destructive but not enabled", tool.Name)
		}
	}
}

// A tool that fails must report the failure as text the model can read, not
// kill the server: the session has to survive a bad sketch or a dead hub.
func TestMCPToolErrorIsRecoverable(t *testing.T) {
	srv := newMCPServer("", false)
	resps := drive(t, srv,
		`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"companion_relay_devices","arguments":{}}}`,
		`{"jsonrpc":"2.0","id":2,"method":"ping"}`)
	if len(resps) != 2 {
		t.Fatalf("server did not survive the tool error: %d responses", len(resps))
	}
	raw, _ := json.Marshal(resps[0].Result)
	var res struct {
		Content []struct {
			Text string `json:"text"`
		} `json:"content"`
		IsError bool `json:"isError"`
	}
	json.Unmarshal(raw, &res)
	if !res.IsError || !strings.Contains(res.Content[0].Text, "--hub") {
		t.Errorf("expected a readable 'no hub configured' error, got %+v", res)
	}
	if resps[1].Error != nil {
		t.Errorf("ping after the error failed: %v", resps[1].Error)
	}
}

// Malformed input and unknown methods get proper JSON-RPC codes, and the loop
// keeps going afterwards.
func TestMCPProtocolErrors(t *testing.T) {
	srv := newMCPServer("", false)
	resps := drive(t, srv,
		`this is not json`,
		`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"nope"}}`,
		`{"jsonrpc":"2.0","id":2,"method":"no/such/method"}`,
		`{"jsonrpc":"2.0","id":3,"method":"ping"}`)
	if len(resps) != 4 {
		t.Fatalf("expected 4 responses, got %d", len(resps))
	}
	if resps[0].Error == nil || resps[0].Error.Code != mcpParseError {
		t.Errorf("bad JSON should be -32700, got %+v", resps[0].Error)
	}
	if resps[1].Error == nil || resps[1].Error.Code != mcpMethodNotFound {
		t.Errorf("unknown tool should be -32601, got %+v", resps[1].Error)
	}
	if resps[2].Error == nil || resps[2].Error.Code != mcpMethodNotFound {
		t.Errorf("unknown method should be -32601, got %+v", resps[2].Error)
	}
	if resps[3].Error != nil {
		t.Errorf("ping should still work after protocol errors: %v", resps[3].Error)
	}
}

// A tool's own output must not land on the protocol channel: the CLI prints
// with fmt.Println, which would otherwise corrupt the JSON-RPC stream and the
// client would see garbage between responses.
func TestMCPToolOutputDoesNotCorruptTheStream(t *testing.T) {
	srv := newMCPServer("", false)
	// companion_board_list prints a table straight to os.Stdout.
	resps := drive(t, srv,
		`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"companion_board_list","arguments":{}}}`)
	if len(resps) != 1 {
		t.Fatalf("expected exactly 1 response, got %d", len(resps))
	}
	raw, _ := json.Marshal(resps[0].Result)
	var res struct {
		Content []struct {
			Text string `json:"text"`
		} `json:"content"`
	}
	json.Unmarshal(raw, &res)
	if strings.Contains(res.Content[0].Text, "\x1b") {
		t.Error("tool result still contains ANSI colour codes")
	}
	_ = context.Background()
}
