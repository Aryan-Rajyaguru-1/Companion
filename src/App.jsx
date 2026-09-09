/**
 * App.jsx — Bugs B C D E F H fixed:
 *
 *  B  Flash parsed from result.output.join('\n') not rawOutputRef.current (race)
 *  C  handleNewTab / handleTemplateSelect / openFile: single setTabs updater
 *  D  inFlightRef = synchronous in-flight lock (prevents double-compile race)
 *  E  saveCurrentTab sends saveCompleted() IPC after save for main.js close handler
 *  F  Stable menu handlers in one-time effect; volatile (save/saveAs) in own effect
 *  H  handleUpload uses compile then uploadBinary — two separate IPC calls
 *     with cancel checkpoint between stages
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import Split            from 'react-split';
import Toolbar          from './components/Toolbar';
import TabBar           from './components/TabBar';
import Editor           from './components/Editor';
import Console          from './components/Console';
import ErrorList        from './components/ErrorList';
import SerialMonitor    from './components/SerialMonitor';
import SerialPlotter    from './components/SerialPlotter';
import BridgeSettings   from './components/BridgeSettings';
import BoardManager     from './components/BoardManager';
import LibraryManager   from './components/LibraryManager';
import Preferences      from './components/Preferences';
import StatusBar        from './components/StatusBar';
import SketchSidebar    from './components/SketchSidebar';
import UploadProgress   from './components/UploadProgress';
import CLISetup         from './components/CLISetup';
import AutoCorrectPanel from './components/AutoCorrectPanel';
import CompileProgress  from './components/CompileProgress';
import SketchTemplates  from './components/SketchTemplates';
import LibraryResolver  from './components/LibraryResolver';
import BoardAutoDetect  from './components/BoardAutoDetect';
import FlashUsageBar    from './components/FlashUsageBar';

import { prefs }                       from './utils/prefs';
import { mcuFromFQBN, normalizeFQBN }  from './utils/fqbn';
import { parseFlashUsage }             from './utils/flash-parser';
import {
  parseCompilerErrors, parseJsonDiagnostics,
  mergeErrors, errorsToMarkers, errorSummary,
} from './utils/error-parser';
import { hasAutoFix }    from './utils/auto-correct';
import { addRecentFile } from './utils/recent-files';
import './App.css';

const DEFAULT_SKETCH = `/*
 * Companion IDE — Wireless Arduino Programmer
 */

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  Serial.println("Hello from Companion IDE!");
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}
`;

let tabIdSeq = 1;
const newTab = (name = 'sketch.ino', code = DEFAULT_SKETCH, path = null) => ({
  id: tabIdSeq++, name, code, path, modified: false,
});

export default function App() {
  // ── Tabs ───────────────────────────────────────────────────
  const [tabs,         setTabs]         = useState([newTab()]);
  const [activeTabIdx, setActiveTabIdx] = useState(0);
  const activeTab = tabs[activeTabIdx] || tabs[0];

  // Stable refs to latest values for use inside stable callbacks
  const tabsRef         = useRef(tabs);
  const activeTabIdxRef = useRef(activeTabIdx);
  const activeTabRef    = useRef(activeTab);
  useEffect(() => { tabsRef.current = tabs; },         [tabs]);
  useEffect(() => { activeTabIdxRef.current = activeTabIdx; }, [activeTabIdx]);
  useEffect(() => { activeTabRef.current = activeTab; },       [activeTab]);

  // ── Panels ─────────────────────────────────────────────────
  const [showSerial,       setShowSerial]      = useState(false);
  const [showPlotter,      setShowPlotter]      = useState(false);
  const [showBridgeConfig, setShowBridgeConfig] = useState(false);
  const [showBoardMgr,     setShowBoardMgr]     = useState(false);
  const [showLibMgr,       setShowLibMgr]       = useState(false);
  const [showPrefs,        setShowPrefs]        = useState(false);
  const [showCLISetup,     setShowCLISetup]     = useState(false);
  const [showSidebar,      setShowSidebar]      = useState(false);
  const [showTemplates,    setShowTemplates]    = useState(false);
  const [showBoardDetect,  setShowBoardDetect]  = useState(false);
  const [showErrorList,    setShowErrorList]    = useState(false);
  const [showAbout,        setShowAbout]        = useState(false);
  const [cliFound,         setCLIFound]         = useState(true);

  // ── Task state ─────────────────────────────────────────────
  const [isCompiling, setIsCompiling] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  // BUG D fix: synchronous in-flight lock — not subject to React state batching
  const inFlightRef = useRef(false);
  const cancelRef   = useRef(null);

  // ── Daemon / cache ─────────────────────────────────────────
  const [daemonRunning,  setDaemonRunning]  = useState(false);
  const [cacheStats,     setCacheStats]     = useState(null);
  const [lastCompileMs,  setLastCompileMs]  = useState(null);

  // ── Cursor ─────────────────────────────────────────────────
  const [cursorLine, setCursorLine] = useState(1);
  const [cursorCol,  setCursorCol]  = useState(1);
  const handleCursorChange = useCallback(({ line, col }) => {
    setCursorLine(line); setCursorCol(col);
  }, []);

  // ── Console ────────────────────────────────────────────────
  const [consoleLogs, setConsoleLogs] = useState([
    { text: '  Companion IDE — Wireless Arduino Programmer\n', type: 'info' },
    { text: '  Connect your ESP32 bridge and press Upload.\n',  type: 'muted' },
    { text: '\n', type: 'output' },
  ]);
  const rawOutputRef = useRef('');

  // ── Errors + Flash ─────────────────────────────────────────
  const [compileErrors,   setCompileErrors]   = useState([]);
  const [compileSummary,  setCompileSummary]  = useState(null);
  const [errorMarkers,    setErrorMarkers]    = useState([]);
  const [showAutoCorrect, setShowAutoCorrect] = useState(false);
  const [showLibResolver, setShowLibResolver] = useState(false);
  const [flashUsage,      setFlashUsage]      = useState(null);

  // ── Settings ───────────────────────────────────────────────
  const [bridgeHost,    setBridgeHostSt]    = useState(localStorage.getItem('bridgeHost')    || 'esp32-bridge.local');
  const [uploadBaud,    setUploadBaudSt]    = useState(Number(localStorage.getItem('uploadBaud')) || 115200);
  // P4c: per-sketch OTA switch (persisted in sketch.yaml profile).
  const [otaEnabled,  setOTAEnabled]  = useState(false);
  const [otaPassword, setOTAPassword] = useState('');
  const [bridgePort,    setBridgePortSt]    = useState(Number(localStorage.getItem('bridgePort'))  || 3333);
  const [selectedBoard, setSelectedBoardSt] = useState(localStorage.getItem('selectedBoard') || 'arduino:avr:uno');
  const [selectedMCU,   setSelectedMCUSt]   = useState(localStorage.getItem('selectedMCU')   || 'avr');
  const [bridgeStatus,  setBridgeStatus]    = useState('disconnected');
  const [installedPlatforms, setInstalledPlatforms] = useState([]);

  // Keep refs for stable callbacks
  const bridgeHostRef   = useRef(bridgeHost);
  const bridgePortRef   = useRef(bridgePort);
  const selectedBoardRef = useRef(selectedBoard);
  const selectedMCURef  = useRef(selectedMCU);
  const uploadBaudRef   = useRef(uploadBaud);
  useEffect(() => { bridgeHostRef.current    = bridgeHost;    }, [bridgeHost]);
  useEffect(() => { bridgePortRef.current    = bridgePort;    }, [bridgePort]);
  useEffect(() => { selectedBoardRef.current = selectedBoard; }, [selectedBoard]);
  useEffect(() => { selectedMCURef.current   = selectedMCU;   }, [selectedMCU]);
  useEffect(() => { uploadBaudRef.current    = uploadBaud;    }, [uploadBaud]);
  const otaEnabledRef  = useRef(otaEnabled);
  const otaPasswordRef = useRef(otaPassword);
  useEffect(() => { otaEnabledRef.current  = otaEnabled;  }, [otaEnabled]);
  useEffect(() => { otaPasswordRef.current = otaPassword; }, [otaPassword]);

  const [autoVerify,   setAutoVerify]    = useState(prefs.get('arduino.upload.autoVerify'));
  const [verboseOut,   setVerboseOut]    = useState(prefs.get('arduino.compile.verbose'));
  const [warnings,     setWarnings]      = useState(prefs.get('arduino.compile.warnings'));
  const [editorSize,   setEditorSize]    = useState(prefs.get('arduino.editor.fontSize'));
  const [wordWrap,     setWordWrap]      = useState(prefs.get('arduino.editor.wordWrap'));
  const [showAllFiles, setShowAllFiles]  = useState(prefs.get('arduino.sketchbook.showAllFiles'));
  const [daemonEnabled,setDaemonEnabled] = useState(prefs.get('companion.daemon.enabled'));

  const editorRef = useRef(null);

  // ── Persist helpers ────────────────────────────────────────
  const setBridgeHost    = v => { setBridgeHostSt(v);    localStorage.setItem('bridgeHost', v); };
  const setBridgePort    = v => { setBridgePortSt(v);    localStorage.setItem('bridgePort', v); };
  const setSelectedBoard = v => {
    const fqbn = normalizeFQBN(v);
    setSelectedBoardSt(fqbn); localStorage.setItem('selectedBoard', fqbn);
    prefs.addRecentFQBN(fqbn);
    const mcu = mcuFromFQBN(fqbn);
    setSelectedMCUSt(mcu); localStorage.setItem('selectedMCU', mcu);
  };
  const setSelectedMCU = v => { setSelectedMCUSt(v); localStorage.setItem('selectedMCU', v); };
  const setUploadBaud  = v => { setUploadBaudSt(v);  localStorage.setItem('uploadBaud', v); };

  // ── Tab helpers ────────────────────────────────────────────
  const updateActiveTab = useCallback(patch =>
    setTabs(prev => prev.map((t, i) => i === activeTabIdxRef.current ? { ...t, ...patch } : t)),
    []);

  const handleCodeChange = useCallback(v => updateActiveTab({ code: v ?? '', modified: true }), [updateActiveTab]);

  const handleTabSelect = useCallback(idx => {
    setActiveTabIdx(idx);
    setShowAutoCorrect(false); setShowLibResolver(false);
  }, []);

  const handleTabClose = useCallback(idx => {
    setTabs(prev => {
      if (prev.length === 1) return [newTab()];
      const next = prev.filter((_, i) => i !== idx);
      setActiveTabIdx(cur => Math.min(cur, next.length - 1));
      return next;
    });
  }, []);

  // BUG C fix: single setTabs updater — correct index regardless of batching
  const handleNewTab = useCallback(() => {
    if (prefs.get('companion.templates.showOnNew')) { setShowTemplates(true); return; }
    setTabs(prev => {
      const next = [...prev, newTab()];
      setActiveTabIdx(next.length - 1); // BUG C
      return next;
    });
  }, []);

  // BUG C fix: single updater
  const handleTemplateSelect = useCallback(({ name, code }) => {
    setTabs(prev => {
      const next = [...prev, newTab(name, code, null)];
      setActiveTabIdx(next.length - 1); // BUG C
      return next;
    });
    setShowTemplates(false);
  }, []);

  // BUG C fix: single updater
  const openFile = useCallback(async (filePath, fileName) => {
    if (!filePath) return;
    const tabs = tabsRef.current;
    const existing = tabs.findIndex(t => t.path === filePath);
    if (existing >= 0) { setActiveTabIdx(existing); return; }
    const r = await window.electronAPI?.readSketchFile?.(filePath);
    if (!r?.success) return;
    const name = fileName || filePath.split(/[/\\]/).pop();
    addRecentFile(filePath, name);
    setTabs(prev => {
      const next = [...prev, newTab(name, r.content, filePath)];
      setActiveTabIdx(next.length - 1); // BUG C
      return next;
    });
  }, []);

  // ── Console ────────────────────────────────────────────────
  const appendConsole = useCallback((text, type = 'output') => {
    rawOutputRef.current += text;
    setConsoleLogs(prev => [...prev.slice(-2000), { text, type }]);
  }, []);

  const clearConsole = useCallback(() => {
    setConsoleLogs([]); rawOutputRef.current = '';
    setErrorMarkers([]); setCompileErrors([]); setCompileSummary(null);
    setShowAutoCorrect(false); setShowLibResolver(false);
    setShowErrorList(false); setFlashUsage(null);
  }, []);

  // ── BUG E fix: saveCurrentTab sends saveCompleted IPC ──────
  // Only signals completion when the save ACTUALLY succeeded. A cancelled
  // Save As dialog (or failed write) now signals save:aborted so main.js
  // keeps the window open instead of destroying it with unsaved changes.
  const saveCurrentTab = useCallback(async () => {
    const tab = tabsRef.current[activeTabIdxRef.current];
    if (!tab) { window.electronAPI?.saveCompleted?.(); return; }

    if (!tab.path) {
      let r = null;
      try { r = await window.electronAPI?.fileSaveAs({ content: tab.code, defaultName: tab.name }); }
      catch { r = { success: false, error: 'Save As failed' }; }
      if (!r?.success) {
        window.electronAPI?.saveAborted?.();
        return;
      }
      addRecentFile(r.path, r.path.split(/[/\\]/).pop());
      updateActiveTab({ path: r.path, name: r.path.split(/[/\\]/).pop(), modified: false });
    } else {
      let ok = true;
      try {
        const r = await window.electronAPI?.fileSave({ path: tab.path, content: tab.code });
        ok = r == null || r.success !== false;
      } catch { ok = false; }
      if (!ok) {
        window.electronAPI?.saveAborted?.();
        return;
      }
      updateActiveTab({ modified: false });
    }
    // BUG E: signal main.js that save is done — allows safe window close
    window.electronAPI?.saveCompleted?.();
  }, [updateActiveTab]);

  const getTempSketchDir = useCallback(async () => {
    const tab = activeTabRef.current;
    const tmp = await window.electronAPI?.getTempDir() || '/tmp';
    // Bug-16 fix: unique dir per compile (mkdtemp) so parallel/instanced
    // compiles never overwrite each other's sketch.
    const name = (tab?.name || 'sketch').replace(/\.ino$/i, '').replace(/[^A-Za-z0-9_-]/g, '_');
    let dir;
    try {
      dir = await window.electronAPI?.mkTempDir(`${tmp}`, `companion_${name}_`);
    } catch { dir = null; }
    if (!dir) {
      // Fallback: unique-ish suffix without a new IPC
      dir = `${tmp}/companion_${name}_${Date.now().toString(36)}`;
    }
    await window.electronAPI?.fileSave({ path: `${dir}/${name}.ino`, content: tab?.code || '' });
    return dir;
  }, []);

  // ── Sketch folder / export ─────────────────────────────────
  const handleShowSketchFolder = useCallback(() => {
    const tab = activeTabRef.current;
    const dir = tab?.path?.replace(/[/\\][^/\\]+$/, '');
    if (dir) window.electronAPI?.openFolder?.(dir);
  }, []);

  const handleExportBinary = useCallback(async () => {
    if (inFlightRef.current) return;
    clearConsole(); setShowErrorList(false);
    appendConsole('» Exporting compiled binary…\n', 'info');
    inFlightRef.current = true; setIsCompiling(true);
    await saveCurrentTab();
    const tab = activeTabRef.current;
    const dir = tab?.path?.replace(/[/\\][^/\\]+$/, '') || await getTempSketchDir();
    const r = await window.electronAPI?.compile({
      sketchDir: dir, fqbn: selectedBoardRef.current,
      exportBin: true, verbose: false, warnings: 'default', json: true,
    });
    inFlightRef.current = false; setIsCompiling(false);
    if (r?.success) appendConsole('✓ Binary exported to sketch/build/\n', 'success');
    else appendConsole(`✗ Export failed: ${r?.error || 'unknown'}\n`, 'error');
  }, [clearConsole, appendConsole, saveCurrentTab, getTempSketchDir]);

  // ── BUG D fix: inFlightRef as synchronous compile lock ─────
  const handleCompile = useCallback(async (silent = false) => {
    // BUG D: synchronous check — not subject to React batching
    if (inFlightRef.current) return null;
    inFlightRef.current = true;

    setIsCompiling(true);
    setShowAutoCorrect(false); setShowLibResolver(false);
    setShowErrorList(false); setFlashUsage(null);
    if (!silent) clearConsole();
    rawOutputRef.current = '';
    appendConsole('» Verifying sketch…\n', 'info');

    // Validate board selection
    if (!selectedBoardRef.current) {
      inFlightRef.current = false;
      setIsCompiling(false);
      appendConsole('✗ No board selected. Choose a board in the toolbar.\n', 'error');
      return null;
    }

    await saveCurrentTab();
    const tab = activeTabRef.current;
    const dir = tab?.path?.replace(/[/\\][^/\\]+$/, '') || await getTempSketchDir();

    cancelRef.current = () => window.electronAPI?.cancelCompile?.();

    const t0 = Date.now();
    const result = await window.electronAPI?.compile({
      sketchDir: dir, fqbn: selectedBoardRef.current, exportBin: true,
      verbose: prefs.get('arduino.compile.verbose'),
      warnings: prefs.get('arduino.compile.warnings'), json: true,
    });
    const elapsed = Date.now() - t0;
    cancelRef.current  = null;
    inFlightRef.current = false;
    setIsCompiling(false); setLastCompileMs(elapsed);

    if (result?.cancelled) {
      appendConsole('\n⊘ Compile cancelled\n', 'muted');
      return null;
    }

    const regexErrors = parseCompilerErrors(rawOutputRef.current, dir);
    const jsonErrors  = parseJsonDiagnostics(result?.diagnostics || []);
    const errors      = mergeErrors(regexErrors, jsonErrors);
    const summary     = errorSummary(errors);

    setCompileErrors(errors); setCompileSummary(summary);
    setErrorMarkers(errorsToMarkers(errors, tab?.path || tab?.name || 'sketch.ino'));

    if (result?.success) {
      // BUG B fix: parse flash from result.output (complete, not race-prone)
      // result.output is the array of output lines returned in the compile result,
      // guaranteed complete when the await resolves.
      const outputText = (result.output || []).join('\n') || rawOutputRef.current;
      setFlashUsage(parseFlashUsage(outputText));

      if (!silent) {
        appendConsole(`\n✓ Compiled in ${(elapsed / 1000).toFixed(1)}s`, 'success');
        if (result.fromDaemon) appendConsole(' (cache hit)', 'muted');
        if (summary.warnings > 0) appendConsole(` — ${summary.warnings} warning${summary.warnings > 1 ? 's' : ''}`, 'warning');
        appendConsole('\n', 'output');
      }
      refreshCacheStats();
    } else {
      // Compilation failed — show error count or CLI error message
      let failMsg = `\n✗ Compilation failed`;
      if (summary.errors > 0) {
        failMsg += ` — ${summary.errors} error${summary.errors > 1 ? 's' : ''}`;
      } else if (result?.error) {
        failMsg += ` — ${result.error}`;
      }
      appendConsole(`${failMsg}\n`, 'error');
      if (errors.length > 0) {
        setShowErrorList(true); setShowLibResolver(true);
        if (hasAutoFix(errors)) setShowAutoCorrect(true);
        editorRef.current?.goToLine?.(errors[0].line);
      }
    }
    return result;
  }, [clearConsole, appendConsole, saveCurrentTab, getTempSketchDir]);

  const handleCancel = useCallback(() => {
    cancelRef.current?.(); cancelRef.current = null;
  }, []);

  const handleJumpToLine = useCallback((line, file) => {
    if (!line) return;
    let switched = false;
    if (file) {
      const base = file.split(/[/\\]/).pop();
      const idx  = tabsRef.current.findIndex(t => (t.path || t.name || '').includes(base));
      if (idx >= 0 && idx !== activeTabIdxRef.current) {
        setActiveTabIdx(idx);
        switched = true;
      }
    }
    // Bug-17 fix: after switching tabs Monaco swaps documents asynchronously —
    // revealing in the same tick clamps against the stale document. Defer
    // until after the model swap (double rAF covers React render + Monaco).
    if (switched) {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        editorRef.current?.goToLine?.(line);
      }));
    } else {
      editorRef.current?.goToLine?.(line);
    }
  }, []);

  const handleAutoCorrectApply = useCallback((newCode, summary) => {
    updateActiveTab({ code: newCode, modified: true });
    appendConsole(`\n» Auto-corrected:\n${summary}\n`, 'info');
    setShowAutoCorrect(false);
    setTimeout(() => handleCompile(false), 300);
  }, [updateActiveTab, appendConsole, handleCompile]);

  // ── USB upload target state (Step 3) ──────────────────────────
  const [uploadTarget, setUploadTarget] = useState('usb');   // 'usb' | 'wifi'
  const [serialPorts, setSerialPorts]   = useState([]);
  const [selectedPort, setSelectedPort] = useState('');
  const serialPortsRef  = useRef([]);
  const selectedPortRef = useRef('');

  const refreshSerialPorts = useCallback(async () => {
    const r = await window.electronAPI?.listSerialPorts?.();
    if (r?.success) {
      setSerialPorts(r.ports || []);
      serialPortsRef.current = r.ports || [];
      // Auto-select: a single detected port wins; prefer one with an FQBN.
      if (r.ports?.length) {
        const best = r.ports.find(p => p.fqbn) || r.ports[0];
        setSelectedPort(prev => {
          if (prev && r.ports.some(p => p.port === prev)) return prev;
          selectedPortRef.current = best.port;
          return best.port;
        });
        // Auto-suggest board FQBN when detected and user hasn't picked one
        if (best.fqbn && (!selectedBoardRef.current || !selectedBoardRef.current.includes(':'))) {
          setSelectedBoard(best.fqbn);
          appendConsole(`» Detected ${best.boardName || 'board'} on ${best.port} → ${best.fqbn}\n`, 'info');
        }
      }
    }
    return r?.ports || [];
  }, [appendConsole]);

  // Scan once at startup
  useEffect(() => { refreshSerialPorts(); }, []);

  // BUG H fix: split upload — compile first, cancel checkpoint, then upload-binary
  const handleUploadUSB = useCallback(async () => {
    if (inFlightRef.current) return;

    const c = await handleCompile(true);
    if (!c?.success) { appendConsole('\n✗ Upload aborted — fix compile errors first\n', 'error'); return; }
    if (!c?.binaryPath) { appendConsole('\n✗ No binary found after compile\n', 'error'); return; }

    const port = selectedPortRef.current || selectedPort;
    if (!port) {
      appendConsole('\n✗ No USB serial device selected — connect your board and refresh ports\n', 'error');
      setShowBoardDetect(true);
      return;
    }

    inFlightRef.current = true; setIsUploading(true);
    clearConsole();
    appendConsole(`» Uploading via USB → ${port} [${selectedBoardRef.current}]\n`, 'info');
    const r = await window.electronAPI?.uploadUSB?.({
      binaryPath: c.binaryPath,
      fqbn: selectedBoardRef.current,
      serialPort: port,
      baud: uploadBaudRef.current,
    });
    inFlightRef.current = false; setIsUploading(false);
    if (r?.success) appendConsole('\n✓ Upload complete — device is running\n', 'success');
    else appendConsole(`\n✗ Upload failed: ${r?.error || 'unknown'}\n`, 'error');
  }, [handleCompile, clearConsole, appendConsole, selectedPort]);

  // Legacy wireless upload path (WiFi bridge)
  const handleUpload = useCallback(async () => {
    if (uploadTarget === 'usb') return handleUploadUSB();

    if (inFlightRef.current) return;

    if (prefs.get('arduino.upload.autoVerify')) {
      const c = await handleCompile(true);
      if (!c?.success) { appendConsole('\n✗ Upload aborted — fix compile errors first\n', 'error'); return; }
      // BUG H: explicit cancel checkpoint between stages
      if (!c?.binaryPath) { appendConsole('\n✗ No binary found after compile\n', 'error'); return; }

      // Stage 2: wireless upload only (separate IPC) — OTA when enabled for an
    // ESP sketch and a device IP is set (P4c).
      inFlightRef.current = true; setIsUploading(true);
      clearConsole();
      const host = bridgeHostRef.current; const port = bridgePortRef.current;
      const mcu  = selectedMCURef.current; const baud = uploadBaudRef.current;

      if (otaEnabledRef.current && /^(esp32|esp8266):/.test(selectedBoardRef.current || '')) {
        const tab = activeTabRef.current;
        const dir = tab?.path?.replace(/[/\\][^/\\]+$/, '') || await getTempSketchDir();
        appendConsole(`» OTA upload (ArduinoOTA) → ${host} [${selectedBoardRef.current}]\n`, 'info');
        const r = await window.electronAPI?.otaUpload?.(
          { ip: host, sketchDir: dir, password: otaPasswordRef.current },
          line => appendConsole(line, 'info')
        );
        inFlightRef.current = false; setIsUploading(false);
        if (r?.success) appendConsole('\n✓ OTA upload complete — device is running\n', 'success');
        else appendConsole(`\n✗ Upload failed: ${r?.error || 'unknown'}\n`, 'error');
        return;
      }

      appendConsole(`» Uploading wirelessly to ${host}:${port} [${mcu}]\n`, 'info');

      const r = await window.electronAPI?.uploadBinary?.({
        binaryPath: c.binaryPath,
        fqbn: selectedBoardRef.current,
        mcu, host, port, baud,
        verbose: prefs.get('arduino.upload.verbose'),
      });
      inFlightRef.current = false; setIsUploading(false);
      if (r?.success) appendConsole('\n✓ Upload complete — device is running\n', 'success');
      else appendConsole(`\n✗ Upload failed: ${r?.error || 'unknown'}\n`, 'error');
      return;
    }

    // No auto-verify: fall back to legacy combined IPC
    inFlightRef.current = true; setIsUploading(true);
    clearConsole();
    await saveCurrentTab();
    const tab = activeTabRef.current;
    const dir = tab?.path?.replace(/[/\\][^/\\]+$/, '') || await getTempSketchDir();
    const r = await window.electronAPI?.upload({
      sketchDir: dir, fqbn: selectedBoardRef.current,
      mcu: selectedMCURef.current, host: bridgeHostRef.current,
      port: bridgePortRef.current, baud: uploadBaudRef.current,
      verbose: prefs.get('arduino.upload.verbose'),
    });
    inFlightRef.current = false; setIsUploading(false);
    if (r?.success) appendConsole('\n✓ Upload complete — device is running\n', 'success');
    else appendConsole(`\n✗ Upload failed: ${r?.error || 'unknown'}\n`, 'error');
  }, [handleCompile, clearConsole, appendConsole, saveCurrentTab, getTempSketchDir, uploadTarget, handleUploadUSB]);

  // BUG F: pingBridge explicit success check (not ||)
  const pingBridge = useCallback(async () => {
    setBridgeStatus('connecting');
    const host = bridgeHostRef.current; const port = bridgePortRef.current;
    const r = await window.electronAPI?.cliPing?.(host, port);
    if (r?.success) {
      setBridgeStatus('connected');
      appendConsole(`» Bridge: ${r.info}\n`, 'info');
    } else {
      const r2 = await window.electronAPI?.bridgeQuery?.({ host, port });
      if (r2?.success) {
        setBridgeStatus('connected');
        appendConsole(`» Bridge: ${r2.info || 'connected'}\n`, 'info');
      } else {
        setBridgeStatus('disconnected');
        appendConsole(`» Bridge unreachable: ${r?.error || r2?.error || 'no response'}\n`, 'error');
      }
    }
  }, [appendConsole]);

  const refreshCacheStats = useCallback(async () => {
    const [stats, running] = await Promise.all([
      window.electronAPI?.cacheStats?.(),
      window.electronAPI?.isDaemonRunning?.(),
    ]);
    if (stats)       setCacheStats(stats);
    if (running != null) setDaemonRunning(!!running);
  }, []);

  const handleEvictCache = useCallback(async () => {
    const r = await window.electronAPI?.evictCache?.(); await refreshCacheStats(); return r;
  }, [refreshCacheStats]);

  const loadInstalledPlatforms = useCallback(async () => {
    const boards = await window.electronAPI?.getBoards?.() || [];
    const platforms = boards.map(b => {
      const src   = b.fqbn || b.id || '';
      const parts = src.split(':');
      return parts.length >= 2 ? `${parts[0]}:${parts[1]}` : null;
    }).filter(Boolean);
    setInstalledPlatforms([...new Set(platforms)]);
  }, []);

  const handlePrefsSave = useCallback(async (vals) => {
    if (!vals) { setShowPrefs(false); return; }
    const prevDaemon = prefs.get('companion.daemon.enabled');
    const nextDaemon = vals['companion.daemon.enabled'];
    setAutoVerify(vals['arduino.upload.autoVerify']);
    setVerboseOut(vals['arduino.compile.verbose']);
    setWarnings(vals['arduino.compile.warnings']);
    setEditorSize(vals['arduino.editor.fontSize']);
    setWordWrap(vals['arduino.editor.wordWrap']);
    setShowAllFiles(vals['arduino.sketchbook.showAllFiles']);
    setDaemonEnabled(nextDaemon);
    prefs.setMany(vals);
    if (!prevDaemon && nextDaemon) {
      const r = await window.electronAPI?.startDaemon?.();
      if (r?.success) { setDaemonRunning(true); refreshCacheStats(); }
    } else if (prevDaemon && !nextDaemon) {
      window.electronAPI?.stopDaemon?.(); setDaemonRunning(false);
    }
    setShowPrefs(false);
  }, [refreshCacheStats]);

  // ── Unsaved changes protection ─────────────────────────────
  useEffect(() => {
    window.__companionHasUnsaved = () => tabsRef.current.some(t => t.modified);
    return () => { delete window.__companionHasUnsaved; };
  }, []);

  // ── Startup ────────────────────────────────────────────────
  useEffect(() => {
    window.electronAPI?.cliVersion?.()
      .then(v => { const ok = v && !v.includes('not found'); setCLIFound(ok); if (!ok) setShowCLISetup(true); })
      .catch(() => { setCLIFound(false); setShowCLISetup(true); });
    if (prefs.get('companion.daemon.enabled')) {
      window.electronAPI?.startDaemon?.().then(r => { if (r?.success) { setDaemonRunning(true); refreshCacheStats(); } });
    }
    loadInstalledPlatforms();
  }, [refreshCacheStats, loadInstalledPlatforms]);

  useEffect(() => {
    const id = setInterval(refreshCacheStats, 30_000);
    return () => clearInterval(id);
  }, [refreshCacheStats]);

  // BUG F fix: STABLE menu handlers in one-time effect
  // These only reference stable callbacks (refs) — no tab state in deps.
  useEffect(() => {
    const api = window.electronAPI; if (!api) return;
    api.onConsole(({ text, type }) => appendConsole(text, type));

    // BUG 10 fix: single updater pattern
    api.onFileOpen(({ path, content }) => {
      const name = path.split(/[/\\]/).pop();
      addRecentFile(path, name);
      setTabs(prev => {
        const next = [...prev, newTab(name, content, path)];
        setActiveTabIdx(next.length - 1);
        return next;
      });
    });

    const stable = {
      compile:        () => handleCompile(),
      upload:         () => handleUpload(),
      uploadUSB:      () => { setUploadTarget('usb'); handleUploadUSB(); },
      cancel:         () => handleCancel(),
      serialMonitor:  () => { setShowPlotter(false); setShowSerial(p => !p); },
      serialPlotter:  () => { setShowSerial(false);  setShowPlotter(p => !p); },
      bridgeSettings: () => setShowBridgeConfig(true),
      boardManager:   () => { setShowBoardMgr(true); loadInstalledPlatforms(); },
      libManager:     () => setShowLibMgr(true),
      prefs:          () => setShowPrefs(true),
      about:          () => setShowAbout(true),
      sidebar:        () => setShowSidebar(p => !p),
      pingBridge:     () => pingBridge(),
      updateIndex:    () => api.updateIndex?.(),
      updateLibIndex: () => api.updateLibIndex?.(),
      format:         () => editorRef.current?.formatDocument?.(),
      find:           () => editorRef.current?.findWidget?.(),
      replace:        () => editorRef.current?.replaceWidget?.(),
      goto:           () => editorRef.current?.goToLineWidget?.(),
      newTemplate:    () => setShowTemplates(true),
      exportBinary:   () => handleExportBinary(),
      sketchFolder:   () => handleShowSketchFolder(),
      new:            () => handleNewTab(),
    };
    Object.entries(stable).forEach(([ev, fn]) => api.onMenu(ev, fn));
    return () => {
      api.offConsole();
      api.offFileOpen();
      Object.keys(stable).forEach(ev => api.offMenu(ev));
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // STABLE: empty deps — only registered once

  // BUG F fix: VOLATILE handlers — re-register only when active tab changes
  useEffect(() => {
    const api = window.electronAPI; if (!api) return;
    const volatile = {
      save:   () => saveCurrentTab(),
      saveAs: async () => {
        const tab = activeTabRef.current;
        const r   = await window.electronAPI?.fileSaveAs({ content: tab?.code || '', defaultName: tab?.name || 'sketch.ino' });
        if (r?.success) updateActiveTab({ path: r.path, name: r.path.split(/[/\\]/).pop(), modified: false });
        window.electronAPI?.saveCompleted?.();
      },
    };
    Object.entries(volatile).forEach(([ev, fn]) => api.onMenu(ev, fn));
    return () => Object.keys(volatile).forEach(ev => api.offMenu(ev));
  }, [saveCurrentTab, updateActiveTab]); // minimal volatile deps

  const sketchDir   = activeTab?.path?.replace(/[/\\][^/\\]+$/, '') || null;
  const extraPanels = [showSerial, showPlotter].filter(Boolean).length;
  const sizes       = extraPanels === 2 ? [42,21,18,19] : extraPanels === 1 ? [56,22,22] : [65,35];
  const minSizes    = extraPanels === 2 ? [160,80,80,80] : extraPanels === 1 ? [160,80,90] : [160,80];

  // Debug logging
  console.log('App component rendering, activeTab:', activeTab?.name);

  return (
    <div className="app-root">
      {/* DIAGNOSTIC: Check if Toolbar renders */}
      <Toolbar
        fileName={activeTab?.name || 'sketch.ino'} modified={activeTab?.modified || false}
        isCompiling={isCompiling} isUploading={isUploading}
        bridgeStatus={bridgeStatus} selectedBoard={selectedBoard}
        selectedMCU={selectedMCU} bridgeHost={bridgeHost}
        autoVerify={autoVerify} verboseOutput={verboseOut}
        compileSummary={compileSummary} daemonRunning={daemonRunning}
        lastCompileMs={lastCompileMs} installedPlatforms={installedPlatforms}
        uploadTarget={uploadTarget} onUploadTargetChange={setUploadTarget}
        serialPorts={serialPorts} selectedPort={selectedPort}
        onPortChange={(p) => { setSelectedPort(p); selectedPortRef.current = p; }}
        onRefreshPorts={() => refreshSerialPorts()}
        onCompile={() => handleCompile()} onUpload={handleUpload} onCancel={handleCancel}
        onToggleSerial={() => { setShowPlotter(false); setShowSerial(p => !p); }}
        onTogglePlotter={() => { setShowSerial(false); setShowPlotter(p => !p); }}
        onToggleSidebar={() => setShowSidebar(p => !p)}
        onNewTemplate={() => setShowTemplates(true)}
        onShowBoardDetect={() => setShowBoardDetect(true)}
        onShowBridgeConfig={() => setShowBridgeConfig(true)}
        onBoardChange={setSelectedBoard} onMCUChange={setSelectedMCU}
        onPingBridge={pingBridge} onShowPrefs={() => setShowPrefs(true)}
        serialActive={showSerial} plotterActive={showPlotter} sidebarActive={showSidebar}
      />

      <div className="app-body">
        <div className="app-main">
          {showSidebar && (
            <SketchSidebar sketchDir={sketchDir} activeFile={activeTab?.path}
              onOpenFile={openFile} onClose={() => setShowSidebar(false)} showAllFiles={showAllFiles} />
          )}
          <div className="app-editor-area">
            <TabBar tabs={tabs} activeIndex={activeTabIdx}
              onSelect={handleTabSelect} onClose={handleTabClose} onNew={handleNewTab} />
            <Split className="split-v" direction="vertical"
              sizes={sizes} minSize={minSizes} gutterSize={5} snapOffset={20}>
              <Editor ref={editorRef} value={activeTab?.code || ''}
                onChange={handleCodeChange} fontSize={editorSize} wordWrap={wordWrap}
                errorMarkers={errorMarkers} onCursorChange={handleCursorChange} />
              <div className="console-area">
                <CompileProgress isCompiling={isCompiling} consoleLogs={consoleLogs} />
                {flashUsage && !isCompiling && <FlashUsageBar flash={flashUsage.flash} ram={flashUsage.ram} />}
                {showErrorList && compileErrors.length > 0 && (
                  <ErrorList errors={compileErrors} onJumpToLine={handleJumpToLine} onDismiss={() => setShowErrorList(false)} />
                )}
                {showLibResolver && compileErrors.length > 0 && (
                  <LibraryResolver errors={compileErrors} sourceCode={activeTab?.code || ''}
                    onInstallComplete={() => { setShowLibResolver(false); handleCompile(false); }}
                    onDismiss={() => setShowLibResolver(false)} />
                )}
                {showAutoCorrect && compileErrors.length > 0 && (
                  <AutoCorrectPanel sourceCode={activeTab?.code || ''} compileErrors={compileErrors}
                    filePath={activeTab?.path || activeTab?.name || 'sketch.ino'}
                    onApply={handleAutoCorrectApply} onDismiss={() => setShowAutoCorrect(false)} />
                )}
                <Console lines={consoleLogs} onClear={clearConsole}
                  compileSummary={compileSummary} onJumpToLine={handleJumpToLine} />
              </div>
              {showSerial  && <SerialMonitor host={bridgeHost} port={bridgePort} onClose={() => setShowSerial(false)} onTearOff={() => setShowSerial(false)} />}
              {showPlotter && <SerialPlotter host={bridgeHost} port={bridgePort} onClose={() => setShowPlotter(false)} />}
            </Split>
          </div>
        </div>
      </div>

      <UploadProgress isCompiling={isCompiling} isUploading={isUploading}
        consoleLogs={consoleLogs}
        onCancel={(isCompiling || isUploading) ? handleCancel : null} />

      <StatusBar fileName={activeTab?.name || 'sketch.ino'} modified={activeTab?.modified || false}
        board={selectedBoard} mcu={selectedMCU} bridgeHost={bridgeHost} bridgeStatus={bridgeStatus}
        isCompiling={isCompiling} isUploading={isUploading} autoVerify={autoVerify} warnings={warnings}
        compileSummary={compileSummary} daemonRunning={daemonRunning} cacheStats={cacheStats}
        lastCompileMs={lastCompileMs} cursorLine={cursorLine} cursorCol={cursorCol}
        onShowSketchFolder={activeTab?.path ? handleShowSketchFolder : null}
        onExportBinary={handleExportBinary} />

      {showBridgeConfig && (
        <BridgeSettings host={bridgeHost} port={bridgePort} mcu={selectedMCU} baud={uploadBaud}
          onHostChange={setBridgeHost} onPortChange={setBridgePort}
          onMCUChange={setSelectedMCU} onBaudChange={setUploadBaud}
          onPing={pingBridge} onClose={() => setShowBridgeConfig(false)}
          otaEnabled={otaEnabled} otaPassword={otaPassword}
          onOTAToggleChange={async (enabled) => {
            if (!sketchDir) {
              appendConsole('\n✗ Save/open a sketch first to manage its OTA profile setting\n', 'error');
              return;
            }
            setOTAEnabled(enabled);
            const r = await window.electronAPI?.otaToggle?.({ enabled, sketchDir });
            appendConsole(
              `\n${r?.success ? '✓' : '✗'} OTA ${enabled ? 'enabled' : 'disabled'} for ${sketchDir}${r?.success ? '' : ' — ' + (r?.error || 'failed')}\n`,
              r?.success ? 'success' : 'error'
            );
          }}
          onOTAPasswordChange={setOTAPassword}
          onOpen={async () => {
            if (!sketchDir) { setOTAEnabled(false); return; }
            const r = await window.electronAPI?.otaStatus?.({ sketchDir });
            if (r?.success) setOTAEnabled(r.enabled);
          }}
        />
      )}
      {showBoardMgr  && <BoardManager  onClose={() => { setShowBoardMgr(false);  loadInstalledPlatforms(); }} />}
      {showLibMgr    && <LibraryManager onClose={() => setShowLibMgr(false)} />}
      {showPrefs     && <Preferences   onClose={handlePrefsSave} onEvictCache={handleEvictCache} cacheStats={cacheStats} daemonRunning={daemonRunning} />}
      {showCLISetup  && <CLISetup      onClose={() => setShowCLISetup(false)} cliFound={cliFound} />}
      {showTemplates && <SketchTemplates onSelect={handleTemplateSelect} onClose={() => setShowTemplates(false)} currentFQBN={selectedBoard} />}
      {showBoardDetect && (
        <BoardAutoDetect currentFQBN={selectedBoard}
          onSelect={(fqbn, mcu) => { setSelectedBoard(fqbn); setSelectedMCU(mcu); setShowBoardDetect(false); loadInstalledPlatforms(); }}
          onClose={() => setShowBoardDetect(false)} />
      )}
      {showAbout && (
        <div className="modal-backdrop" onClick={() => setShowAbout(false)}>
          <div className="modal about-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">About Companion IDE</span>
              <button className="modal-close" onClick={() => setShowAbout(false)}>✕</button>
            </div>
            <div className="about-body">
              <div className="about-logo">📡</div>
              <h2>Companion IDE</h2>
              <p>Wireless Arduino Programmer</p>
              <p className="about-desc">Upload sketches over WiFi — no USB cable required.</p>
              <div className="about-links">
                <a href="https://github.com/companion-ide/companion-ide" target="_blank" rel="noreferrer">GitHub</a>
                <a href="https://docs.arduino.cc/language-reference/" target="_blank" rel="noreferrer">Arduino Reference</a>
              </div>
              <button className="btn btn-primary" style={{marginTop:8}} onClick={() => setShowAbout(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
