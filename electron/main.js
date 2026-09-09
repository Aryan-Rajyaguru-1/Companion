/**
 * main.js
 * Bug E fix: before-close "Save" path sends menu:save then waits for
 *   save:completed IPC from renderer before destroying window — no fixed timeout.
 * Bug H fix: arduino:upload-binary IPC handles only wireless upload (no compile),
 *   so UI can check state and offer cancel between stages.
 */

console.log('=== ELECTRON MAIN.JS STARTING ===');

const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require('electron');
const path  = require('path');
const fs    = require('fs');
const os    = require('os');

// Disable GPU acceleration on ARM64 systems (Jetson) to prevent crashes
app.disableHardwareAcceleration();

const CompanionCLI = require('./companion-cli');
const BridgeClient = require('./bridge-client');

const isDev = process.env.NODE_ENV === 'development';
console.log('isDev:', isDev);
let mainWindow;
let monitorWindow = null; // P5 #11: tear-off serial-monitor window (single instance)
const companionCLI = new CompanionCLI();
const bridgeClient = new BridgeClient();

// ── Window ─────────────────────────────────────────────────────
function createWindow() {
  console.log('createWindow() called');
  mainWindow = new BrowserWindow({
    width: 1280, height: 820, minWidth: 900, minHeight: 600,
    backgroundColor: '#1a1e24',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, sandbox: false,
    },
  });

  console.log('BrowserWindow created');

  // BUG E FIX: wait for save:completed IPC instead of using a fixed timeout
  mainWindow.on('close', async (e) => {
    e.preventDefault();

    const hasUnsaved = await mainWindow.webContents
      .executeJavaScript('window.__companionHasUnsaved ? window.__companionHasUnsaved() : false')
      .catch(() => false);

    if (!hasUnsaved) { mainWindow.destroy(); return; }

    const { response } = await dialog.showMessageBox(mainWindow, {
      type: 'question',
      buttons: ['Save', "Don't Save", 'Cancel'],
      defaultId: 0, cancelId: 2,
      title: 'Unsaved Changes',
      message: 'You have unsaved changes. Save before closing?',
    });

    if (response === 2) return; // Cancel
    if (response === 1) { mainWindow.destroy(); return; } // Don't Save

    // BUG E FIX: Register a one-shot listener for save:completed
    // then send the save command. Destroy only after confirmation arrives.
    const onSaveCompleted = () => {
      clearTimeout(fallback);
      mainWindow?.destroy();
    };
    // Save aborted (user cancelled the dialog, or write failed):
    // keep the window open so unsaved changes are not lost.
    const onSaveAborted = () => {
      ipcMain.removeListener('save:completed', onSaveCompleted);
      clearTimeout(fallback);
    };
    ipcMain.once('save:completed', onSaveCompleted);
    ipcMain.once('save:aborted', onSaveAborted);

    mainWindow.webContents.send('menu:save');

    // Safety fallback: destroy after 10s if neither IPC ever fires
    const fallback = setTimeout(() => {
      ipcMain.removeListener('save:completed', onSaveCompleted);
      ipcMain.removeListener('save:aborted', onSaveAborted);
      mainWindow?.destroy();
    }, 10_000);
  });

  if (isDev) {
    console.log('Loading dev URL: http://localhost:5173');
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'bottom' });
    console.log('Dev tools opened');
  } else {
    const distPath = path.join(__dirname, '..', 'dist', 'index.html');
    console.log('Loading production file:', distPath);
    mainWindow.loadFile(distPath);
  }
  mainWindow.on('closed', () => { mainWindow = null; });
  console.log('Window loaded and event handlers set up');
}

app.whenReady().then(() => { createWindow(); buildMenu(); registerIPC(); });
app.on('window-all-closed', () => {
  bridgeClient.disconnectSerial();
  companionCLI.stopDaemon();
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

// ── Menu ───────────────────────────────────────────────────────
function buildMenu() {
  const send = (ev) => mainWindow?.webContents.send(`menu:${ev}`);
  const template = [
    {
      label: 'File', submenu: [
        { label: 'New Sketch',        accelerator: 'CmdOrCtrl+N',       click: () => send('new')         },
        { label: 'New from Template…',                                   click: () => send('newTemplate') },
        { label: 'Open…',             accelerator: 'CmdOrCtrl+O',       click: () => openFileDialog()    },
        { label: 'Save',              accelerator: 'CmdOrCtrl+S',       click: () => send('save')        },
        { label: 'Save As…',          accelerator: 'CmdOrCtrl+Shift+S', click: () => send('saveAs')      },
        { type: 'separator' },
        { label: 'Preferences',       accelerator: 'CmdOrCtrl+,',       click: () => send('prefs')       },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'Edit', submenu: [
        { role: 'undo' }, { role: 'redo' }, { type: 'separator' },
        { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' },
        { type: 'separator' },
        { label: 'Find',            accelerator: 'CmdOrCtrl+F',       click: () => send('find')    },
        { label: 'Find & Replace',  accelerator: 'CmdOrCtrl+H',       click: () => send('replace') },
        { label: 'Go to Line…',     accelerator: 'CmdOrCtrl+G',       click: () => send('goto')    },
        { type: 'separator' },
        { label: 'Format Document', accelerator: 'CmdOrCtrl+Shift+F', click: () => send('format')  },
      ],
    },
    {
      label: 'Sketch', submenu: [
        { label: 'Verify / Compile',      accelerator: 'CmdOrCtrl+R', click: () => send('compile')      },
        { label: 'Upload via USB',        accelerator: 'CmdOrCtrl+Shift+U', click: () => send('uploadUSB') },
        { label: 'Upload via WiFi',       accelerator: 'CmdOrCtrl+U', click: () => send('upload')       },
        { label: 'Cancel',                 accelerator: 'CmdOrCtrl+.', click: () => send('cancel')       },
        { type: 'separator' },
        { label: 'Export Compiled Binary',                              click: () => send('exportBinary') },
        { label: 'Show Sketch Folder',     accelerator: 'CmdOrCtrl+K', click: () => send('sketchFolder') },
        { type: 'separator' },
        { label: 'Board Manager…',                                      click: () => send('boardManager') },
        { label: 'Library Manager…',                                    click: () => send('libManager')   },
      ],
    },
    {
      label: 'Tools', submenu: [
        { label: 'Serial Monitor',  accelerator: 'CmdOrCtrl+Shift+M', click: () => send('serialMonitor')  },
        { label: 'Serial Plotter',  accelerator: 'CmdOrCtrl+Shift+L', click: () => send('serialPlotter')  },
        { label: 'Toggle Sidebar',  accelerator: 'CmdOrCtrl+Shift+E', click: () => send('sidebar')        },
        { type: 'separator' },
        { label: 'WiFi Bridge Settings',                                click: () => send('bridgeSettings') },
        { label: 'Ping Bridge',                                         click: () => send('pingBridge')     },
        { type: 'separator' },
        { label: 'Update Board Index',                                  click: () => send('updateIndex')    },
        { label: 'Update Library Index',                                click: () => send('updateLibIndex') },
      ],
    },
    {
      label: 'Help', submenu: [
        { label: 'Arduino Language Reference', click: () => shell.openExternal('https://docs.arduino.cc/language-reference/') },
        { label: 'Companion IDE on GitHub',    click: () => shell.openExternal('https://github.com/companion-ide/companion-ide') },
        { type: 'separator' },
        { label: 'About Companion IDE',        click: () => send('about') },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function openFileDialog() {
  const result = await dialog.showOpenDialog(mainWindow, {
    filters: [
      { name: 'Arduino Sketch', extensions: ['ino'] },
      { name: 'C/C++ Source',   extensions: ['cpp','c','h','hpp'] },
      { name: 'All Files',      extensions: ['*'] },
    ],
    properties: ['openFile'],
  });
  if (!result.canceled && result.filePaths.length > 0) {
    const fp = result.filePaths[0];
    mainWindow?.webContents.send('file:opened', { path: fp, content: fs.readFileSync(fp, 'utf-8') });
  }
}

// ── IPC ────────────────────────────────────────────────────────
function registerIPC() {
  const emit = (line) => mainWindow?.webContents.send('console:line', { text: line, type: 'output' });

  // OS
  ipcMain.handle('os:tempdir', () => os.tmpdir());
  // Unique temp dir per compile (fs.mkdtemp) — prevents two IDE instances
  // or parallel compiles from overwriting each other's sketch
  ipcMain.handle('os:mkdtemp', (_, { prefix }) => fs.mkdtempSync(prefix || (os.tmpdir() + '/companion_')));

  // BUG E FIX: renderer sends this after save completes; the close handler
  // registers its own ipcMain.once('save:completed') listener on demand.
  ipcMain.on('save:completed', () => {});

  // File ops
  ipcMain.handle('file:save', async (_, { path: p, content }) => {
    try { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, content, 'utf-8'); return { success: true }; }
    catch (e) { return { success: false, error: e.message }; }
  });
  ipcMain.handle('file:saveAs', async (_, { content, defaultName = 'sketch.ino' }) => {
    try {
      const r = await dialog.showSaveDialog(mainWindow, {
        defaultPath: path.join(os.homedir(), 'CompanionSketches', defaultName),
        filters: [{ name: 'Arduino Sketch', extensions: ['ino'] }],
      });
      if (r.canceled) return { success: false };
      fs.mkdirSync(path.dirname(r.filePath), { recursive: true });
      fs.writeFileSync(r.filePath, content, 'utf-8');
      return { success: true, path: r.filePath };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });
  ipcMain.handle('file:open', async () => {
    const r = await dialog.showOpenDialog(mainWindow, {
      filters: [{ name: 'Arduino Sketch', extensions: ['ino','cpp','c','h'] }],
      properties: ['openFile'],
    });
    if (r.canceled) return null;
    const p = r.filePaths[0];
    return { path: p, content: fs.readFileSync(p, 'utf-8') };
  });
  ipcMain.handle('file:listSketchFiles', async (_, { dir, showAll = false }) => {
    try {
      if (!dir || !fs.existsSync(dir)) return [];
      const CORE = new Set(['ino','cpp','c','h','hpp','s']);
      const EXTRA = new Set(['txt','md','json','yaml','yml']);
      return fs.readdirSync(dir, { withFileTypes: true })
        .filter(e => e.isFile() && !e.name.startsWith('.'))
        .filter(e => { const ext = (e.name.split('.').pop() || '').toLowerCase(); return CORE.has(ext) || (showAll && EXTRA.has(ext)); })
        .map(e => { const fp = path.join(dir, e.name); let size = null; try { size = fs.statSync(fp).size; } catch {} return { name: e.name, path: fp, size }; })
        .sort((a, b) => { const ai = a.name.endsWith('.ino') ? 0 : 1, bi = b.name.endsWith('.ino') ? 0 : 1; return ai !== bi ? ai - bi : a.name.localeCompare(b.name); });
    } catch { return []; }
  });
  ipcMain.handle('file:readSketch', async (_, { path: p }) => {
    try { return { success: true, content: fs.readFileSync(p, 'utf-8') }; }
    catch (e) { return { success: false, error: e.message }; }
  });
  ipcMain.handle('file:openFolder', async (_, { dir }) => {
    try { shell.openPath(dir); return { success: true }; }
    catch (e) { return { success: false, error: e.message }; }
  });

  // Daemon
  ipcMain.handle('daemon:start',     async () => companionCLI.startDaemon(line => mainWindow?.webContents.send('console:line', { text: line, type: 'muted' })));
  ipcMain.handle('daemon:stop',      () => { companionCLI.stopDaemon(); return { success: true }; });
  ipcMain.handle('daemon:isRunning', () => companionCLI.isDaemonRunning());
  ipcMain.handle('daemon:ping',      () => companionCLI.pingDaemon());

  // Cache
  ipcMain.handle('cache:stats',  () => companionCLI.cacheStats());
  ipcMain.handle('cache:evict',  () => companionCLI.evictCache());

  // Cancel (works for both daemon and subprocess)
  ipcMain.handle('arduino:cancel-compile', () => {
    const cancelled = companionCLI.cancelCompile();
    return { cancelled };
  });

  // Compile only (no upload)
  ipcMain.handle('arduino:compile', async (_, { sketchDir, fqbn, exportBin = false, verbose = false, warnings = 'default', json = false }) =>
    companionCLI.compile(sketchDir, fqbn, emit, exportBin, verbose, warnings, json));

  // BUG H FIX: Upload-binary is a separate IPC — only does wireless transfer,
  // not compile. UI calls compile first, checks result, then calls this.
  ipcMain.handle('arduino:upload-binary', async (_, { binaryPath, fqbn, mcu, host, port, baud, verbose }) => {
    if (!binaryPath || !fs.existsSync(binaryPath)) {
      return { success: false, error: `Binary not found: ${binaryPath}` };
    }
    emit(`» Uploading wirelessly to ${host}:${port} [${mcu}]...\n`);
    return bridgeClient.uploadFirmware({ host, port, baud, mcu, avrMcu: BridgeClient.avrMcuForFqbn(fqbn), binaryPath, onProgress: emit });
  });

  // USB upload: flash prebuilt binary over a local serial port.
  // (The CLI handles esptool/avrdude; we just stream its output.)
  ipcMain.handle('arduino:upload-usb', async (_, { binaryPath, fqbn, serialPort, baud }) => {
    if (!binaryPath || !fs.existsSync(binaryPath)) {
      return { success: false, error: `Binary not found: ${binaryPath}` };
    }
    if (!serialPort) return { success: false, error: 'No serial port selected' };
    emit(`» Uploading via USB → ${serialPort} [${fqbn}]\n`);
    return companionCLI.uploadUSB({ binaryPath, fqbn, serialPort, baud }, emit);
  });

  // Serial port detection with board identification
  ipcMain.handle('serial:list-ports', async () => {
    try { return { success: true, ports: await companionCLI.listPorts() }; }
    catch (err) { return { success: false, ports: [], error: err.message }; }
  });

  // Legacy combined compile+upload (kept for compatibility)
  ipcMain.handle('arduino:upload', async (_, { sketchDir, fqbn, mcu, host, port, baud, verbose }) => {
    emit(`» Compiling for wireless upload...\n`);
    const compile = await companionCLI.compile(sketchDir, fqbn, emit, true, verbose);
    if (!compile.success) return { success: false, error: compile.error || 'Compile failed' };
    if (!compile.binaryPath) return { success: false, error: 'Binary not found after compile' };
    emit(`\n» Uploading wirelessly to ${host}:${port} [${mcu}]...\n`);
    return bridgeClient.uploadFirmware({ host, port, baud, mcu, avrMcu: BridgeClient.avrMcuForFqbn(fqbn), binaryPath: compile.binaryPath, onProgress: emit });
  });

  // Boards
  ipcMain.handle('arduino:boards',           async ()      => companionCLI.listBoards());
  ipcMain.handle('arduino:list-all-boards',  async ()      => companionCLI.listAllBoards());
  ipcMain.handle('arduino:search-cores',     async (_, q)  => companionCLI.searchBoards(q));
  ipcMain.handle('arduino:search-packages',  async (_, q)  => companionCLI.searchBoardPackages(q));
  ipcMain.handle('arduino:install-core',     async (_, id) => companionCLI.installCore(id, emit));
  ipcMain.handle('arduino:update-index',     async ()      => companionCLI.updateIndex(emit));

  // Libraries
  ipcMain.handle('arduino:list-libs',        async ()        => companionCLI.listLibraries());
  ipcMain.handle('arduino:search-libs',      async (_, q)    => companionCLI.searchLibraries(q));
  // Lib install: stream to main console AND a dedicated channel that
  // in-modal outputs (LibraryManager) can subscribe to
  ipcMain.handle('arduino:install-lib', async (_, name) => {
    const dual = (line) => {
      emit(line);
      mainWindow?.webContents.send('lib:install:progress', `${line}\n`);
    };
    return companionCLI.installLibrary(name, dual);
  });
  ipcMain.handle('arduino:uninstall-lib',    async (_, name) => companionCLI.uninstallLibrary(name));
  ipcMain.handle('arduino:update-lib-index', async ()        => companionCLI.updateLibIndex(emit));
  ipcMain.handle('arduino:version',          async ()        => companionCLI.version());
  ipcMain.handle('arduino:ping',             async (_, { host, port }) => companionCLI.ping(host, port));

  // Config
  ipcMain.handle('companion:config-get', async (_, key)            => companionCLI.getConfig(key));
  ipcMain.handle('companion:config-set', async (_, { key, value }) => companionCLI.setConfig(key, value));

  // OTA (P4c): per-sketch switch + status + push
  ipcMain.handle('ota:toggle',  async (_, { enabled, sketchDir }) => companionCLI.otaToggle(enabled, sketchDir));
  ipcMain.handle('ota:status',  async (_, { sketchDir })          => companionCLI.otaStatus(sketchDir));
  ipcMain.handle('ota:upload',  async (_, opts) => {
    emit(`» OTA: compiling sketch for wireless flash…\n`);
    const r = await companionCLI.otaUpload(opts, emit);
    if (!r.success && !r.cancelled) emit(`\n✗ OTA failed: ${r.error}\n`);
    return r;
  });

  // Bridge
  ipcMain.handle('bridge:connect-serial', async (_, { host, port }) =>
    bridgeClient.connectSerial(host, port, data => {
      mainWindow?.webContents.send('serial:data', data);
      // P5 #11: also feed a detached serial-monitor window if one is open.
      if (monitorWindow && !monitorWindow.isDestroyed()) {
        monitorWindow.webContents.send('serial:data', data);
      }
    }));
  ipcMain.handle('bridge:disconnect-serial', () => { bridgeClient.disconnectSerial(); return { success: true }; });
  ipcMain.handle('bridge:send',  (_, data) => { bridgeClient.send(data); });
  ipcMain.handle('bridge:query', (_, cfg)  => bridgeClient.query(cfg.host, cfg.port));

  // P5 #11: tear-off the serial monitor into its own window. Single instance —
  // a second request just focuses the existing window.
  ipcMain.handle('monitor:tear-off', (_, { host, port } = {}) => {
    if (monitorWindow && !monitorWindow.isDestroyed()) {
      monitorWindow.focus();
      return { success: true, focused: true };
    }
    const params = new URLSearchParams({ view: 'serial-monitor', host: host || '', port: String(port || '') });
    const qs = params.toString();
    monitorWindow = new BrowserWindow({
      width: 760, height: 560, minWidth: 420, minHeight: 280,
      backgroundColor: '#1a1e24',
      title: 'Serial Monitor',
      autoHideMenuBar: true,
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true, nodeIntegration: false, sandbox: false,
      },
    });
    const devUrl = process.env.VITE_DEV_SERVER_URL;
    if (devUrl) {
      monitorWindow.loadURL(`${devUrl}?${qs}`);
    } else {
      monitorWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'), { query: Object.fromEntries(params) });
    }
    monitorWindow.on('closed', () => { monitorWindow = null; });
    monitorWindow.on('page-title-updated', e => e.preventDefault());
    return { success: true };
  });
}
