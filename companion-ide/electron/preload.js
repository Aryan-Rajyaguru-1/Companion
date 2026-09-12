/**
 * preload.js
 * Bug E: saveCompleted() sends IPC so main.js can destroy window safely.
 * Bug H: uploadBinary() — upload-only IPC (no compile step).
 */
const { contextBridge, ipcRenderer } = require('electron');

const menuListeners = {};

contextBridge.exposeInMainWorld('electronAPI', {
  // ── File ────────────────────────────────────────────────────
  fileSave:        (p)            => ipcRenderer.invoke('file:save', p),
  fileSaveAs:      (p)            => ipcRenderer.invoke('file:saveAs', p),
  fileOpen:        ()             => ipcRenderer.invoke('file:open'),
  getTempDir:      ()             => ipcRenderer.invoke('os:tempdir'),
  mkTempDir:       (dir, prefix)  => ipcRenderer.invoke('os:mkdtemp', { prefix: require('path').join(dir, prefix || 'companion_') }),
  listSketchFiles: (dir, showAll) => ipcRenderer.invoke('file:listSketchFiles', { dir, showAll }),
  readSketchFile:  (fp)           => ipcRenderer.invoke('file:readSketch', { path: fp }),
  openFolder:      (dir)          => ipcRenderer.invoke('file:openFolder', { dir }),

  // BUG E FIX: renderer calls this after save finishes
  saveCompleted:   ()             => ipcRenderer.send('save:completed'),
  // Save failed/cancelled during close — main keeps the window open
  saveAborted:     ()             => ipcRenderer.send('save:aborted'),

  // ── Compile + cancel ─────────────────────────────────────────
  compile:        (p)  => ipcRenderer.invoke('arduino:compile', p),
  cancelCompile:  ()   => ipcRenderer.invoke('arduino:cancel-compile'),

  // BUG H FIX: wireless upload only — no compile step
  uploadBinary:   (p)  => ipcRenderer.invoke('arduino:upload-binary', p),
  // USB upload via local serial port
  uploadUSB:      (p)  => ipcRenderer.invoke('arduino:upload-usb', p),
  // Detect connected serial boards (VID/PID → FQBN)
  listSerialPorts: ()  => ipcRenderer.invoke('serial:list-ports'),
  // Legacy combined (kept for backward compat)
  upload:         (p)  => ipcRenderer.invoke('arduino:upload', p),

  // ── Daemon ───────────────────────────────────────────────────
  startDaemon:     ()  => ipcRenderer.invoke('daemon:start'),
  stopDaemon:      ()  => ipcRenderer.invoke('daemon:stop'),
  isDaemonRunning: ()  => ipcRenderer.invoke('daemon:isRunning'),
  pingDaemon:      ()  => ipcRenderer.invoke('daemon:ping'),

  // ── Cache ────────────────────────────────────────────────────
  cacheStats:  ()  => ipcRenderer.invoke('cache:stats'),
  evictCache:  ()  => ipcRenderer.invoke('cache:evict'),

  // ── Boards ───────────────────────────────────────────────────
  getBoards:       ()    => ipcRenderer.invoke('arduino:boards'),
  // Every board from all installed platforms (Arduino-IDE-style full list)
  getAllBoards:    ()    => ipcRenderer.invoke('arduino:list-all-boards'),
  searchCores:     (q)   => ipcRenderer.invoke('arduino:search-cores', q),
  searchPackages:  (q)   => ipcRenderer.invoke('arduino:search-packages', q),
  installCore:     (id)  => ipcRenderer.invoke('arduino:install-core', id),
  getCompileFlags: (sketchDir, file) => ipcRenderer.invoke('compile:flags', { sketchDir, file }),
  otaDiscover:     (waitMs) => ipcRenderer.invoke('ota:discover', { waitMs }),
  updateIndex:     ()    => ipcRenderer.invoke('arduino:update-index'),

  // ── Libraries ────────────────────────────────────────────────
  listLibs:       ()     => ipcRenderer.invoke('arduino:list-libs'),
  searchLibs:     (q)    => ipcRenderer.invoke('arduino:search-libs', q),
  // Lib install progress: streamed on its own channel so panels can subscribe
  installLib:     (name, onProgress) => {
    if (!onProgress) return ipcRenderer.invoke('arduino:install-lib', name);
    const handler = (_, line) => onProgress(line);
    ipcRenderer.on('lib:install:progress', handler);
    return ipcRenderer.invoke('arduino:install-lib', name)
      .finally(() => ipcRenderer.removeListener('lib:install:progress', handler));
  },
  uninstallLib:   (name) => ipcRenderer.invoke('arduino:uninstall-lib', name),
  updateLibIndex: ()     => ipcRenderer.invoke('arduino:update-lib-index'),

  // ── Version / ping ───────────────────────────────────────────
  cliVersion: ()           => ipcRenderer.invoke('arduino:version'),
  cliPing:    (host, port) => ipcRenderer.invoke('arduino:ping', { host, port }),

  // ── Config ───────────────────────────────────────────────────
  companionConfigGet: (key)        => ipcRenderer.invoke('companion:config-get', key),
  companionConfigSet: (key, value) => ipcRenderer.invoke('companion:config-set', { key, value }),

  // ── Bridge ───────────────────────────────────────────────────
  bridgeQuery:      (cfg)  => ipcRenderer.invoke('bridge:query', cfg),
  bridgeConnect:    (cfg)  => ipcRenderer.invoke('bridge:connect-serial', cfg),
  bridgeDisconnect: ()     => ipcRenderer.invoke('bridge:disconnect-serial'),
  bridgeSend:       (data) => ipcRenderer.invoke('bridge:send', data),

  // ── Streams ──────────────────────────────────────────────────
  onConsole:  (cb) => { ipcRenderer.on('console:line', (_, v) => cb(v)); },
  onSerial:   (cb) => { ipcRenderer.on('serial:data',  (_, v) => cb(v)); },
  onFileOpen: (cb) => { ipcRenderer.on('file:opened',  (_, v) => cb(v)); },

  onMenu: (ev, cb) => {
    const wrapped = (_, ...args) => cb(...args);
    menuListeners[ev] = wrapped;
    ipcRenderer.on(`menu:${ev}`, wrapped);
  },

  // P5 #11: detach the serial monitor into its own window.
  monitorTearOff: (opts) => ipcRenderer.invoke('monitor:tear-off', opts),

  // P4c: per-sketch OTA switch + push
  otaToggle: (opts) => ipcRenderer.invoke('ota:toggle', opts),
  otaStatus: (opts) => ipcRenderer.invoke('ota:status', opts),
  otaUpload: (opts, onOutput) => {
    const send = (_, line) => onOutput?.(line);
    ipcRenderer.on('console:line', send);
    return ipcRenderer.invoke('ota:upload', opts).finally(() => ipcRenderer.removeListener('console:line', send));
  },

  offConsole:  ()  => ipcRenderer.removeAllListeners('console:line'),
  offSerial:   ()  => ipcRenderer.removeAllListeners('serial:data'),
  offFileOpen: ()  => ipcRenderer.removeAllListeners('file:opened'),
  offMenu: (ev) => {
    const fn = menuListeners[ev];
    if (fn) { ipcRenderer.removeListener(`menu:${ev}`, fn); delete menuListeners[ev]; }
    else    { ipcRenderer.removeAllListeners(`menu:${ev}`); }
  },
});
