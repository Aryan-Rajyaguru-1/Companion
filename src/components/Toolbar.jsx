import BoardDropdown from './BoardDropdown';
import './Toolbar.css';

export default function Toolbar({
  fileName, modified, isCompiling, isUploading,
  bridgeStatus, selectedBoard, selectedMCU, bridgeHost,
  autoVerify, verboseOutput, compileSummary,
  daemonRunning, lastCompileMs, installedPlatforms,
  uploadTarget = 'usb', onUploadTargetChange,
  serialPorts = [], selectedPort = '', onPortChange, onRefreshPorts,
  onCompile, onUpload,
  onToggleSerial, onTogglePlotter, onToggleSidebar,
  onNewTemplate, onShowBoardDetect,
  onShowBridgeConfig, onBoardChange, onMCUChange,
  onPingBridge, onShowPrefs,
  serialActive, plotterActive, sidebarActive,
}) {
  const busy = isCompiling || isUploading;
  const statusColor = bridgeStatus === 'connected'  ? 'var(--green)'
                    : bridgeStatus === 'connecting' ? 'var(--yellow)'
                    : 'var(--text-dim)';

  return (
    <div className="toolbar">
      <div className="toolbar-logo">
        <WifiIcon />
        <span className="toolbar-brand">Companion IDE</span>
        {daemonRunning != null && (
          <span className={`tb-daemon-dot ${daemonRunning ? 'on' : 'off'}`}
            title={daemonRunning ? 'CLI daemon active — build cache warm' : 'Daemon not running'} />
        )}
      </div>
      <div className="toolbar-divider" />

      <button className={`tb-btn tb-icon ${sidebarActive ? 'active' : ''}`}
        title="Toggle Explorer  Ctrl+Shift+E" onClick={onToggleSidebar}>
        <SidebarIcon />
      </button>
      <button className="tb-btn tb-icon" title="New from Template" onClick={onNewTemplate}>
        <TemplateIcon />
      </button>
      <div className="toolbar-divider" />

      <button className="tb-btn tb-compile" title="Verify / Compile  Ctrl+R"
        onClick={onCompile} disabled={busy}>
        <VerifyIcon />
        <span className="tb-btn-label">Verify</span>
      </button>

      <button className={`tb-btn tb-upload ${isUploading ? 'uploading' : ''}`}
        title={uploadTarget === 'usb'
          ? 'Upload via USB  Ctrl+Shift+U'
          : 'Upload via WiFi  Ctrl+U'}
        onClick={onUpload} disabled={isCompiling}>
        {isUploading ? <StopIcon /> : <UploadIcon />}
        <span className="tb-btn-label">{isUploading ? 'Stop' : (uploadTarget === 'usb' ? 'USB Upload' : 'WiFi Upload')}</span>
      </button>
      <div className="toolbar-divider" />

      <BoardDropdown
        selectedFqbn={selectedBoard}
        selectedMCU={selectedMCU}
        onSelect={(fqbn, mcu) => { onBoardChange(fqbn); onMCUChange(mcu); }}
        onEditConfig={onShowBridgeConfig}
        onDetectBoards={onShowBoardDetect}
        installedPlatforms={installedPlatforms || []}
      />
      <div className="toolbar-divider" />

      {/* Upload target: USB ⇄ WiFi */}
      <div className="tb-target-toggle" title="Upload transport">
        <button className={`tb-tgt ${uploadTarget === 'usb' ? 'on' : ''}`}
          onClick={() => onUploadTargetChange?.('usb')}>USB</button>
        <button className={`tb-tgt ${uploadTarget === 'wifi' ? 'on' : ''}`}
          onClick={() => onUploadTargetChange?.('wifi')}>WiFi</button>
      </div>

      {uploadTarget === 'usb' ? (
        <div className="tb-port-picker">
          <select className="tb-port-select" value={selectedPort}
            onChange={e => onPortChange?.(e.target.value)}>
            {serialPorts.length === 0 && (
              <option value="">No devices — refresh</option>
            )}
            {serialPorts.map(p => (
              <option key={p.port} value={p.port}>
                {p.port}{p.boardName ? ` — ${p.boardName}` : (p.productName ? ` — ${p.productName}` : '')}
              </option>
            ))}
          </select>
          <button className="tb-btn tb-icon" title="Rescan serial ports"
            onClick={() => onRefreshPorts?.()}>
            ⟳
          </button>
        </div>
      ) : (
        <button className={`tb-btn tb-bridge-btn ${bridgeStatus}`}
          onClick={onPingBridge}
          title={`Bridge ${bridgeStatus} — ${bridgeHost} — click to ping`}>
          <span className="status-dot" style={{
            background: statusColor,
            boxShadow: bridgeStatus === 'connected' ? `0 0 4px ${statusColor}` : 'none',
          }} />
          <span className="tb-bridge-host">
            {bridgeStatus === 'connected'   ? bridgeHost
             : bridgeStatus === 'connecting' ? 'Connecting…'
             : 'Bridge offline'}
          </span>
        </button>
      )}

      <button className="tb-btn tb-icon" title="Preferences  Ctrl+," onClick={onShowPrefs}>
        <GearIcon />
      </button>

      <div className="toolbar-spacer" />

      {compileSummary && !busy && compileSummary.errors > 0 && (
        <span className="tb-badge tb-badge-err">✗ {compileSummary.errors}</span>
      )}
      {compileSummary && !busy && compileSummary.warnings > 0 && (
        <span className="tb-badge tb-badge-warn">⚠ {compileSummary.warnings}</span>
      )}
      {compileSummary && !busy && compileSummary.errors === 0 && compileSummary.warnings === 0 && (
        <span className="tb-badge tb-badge-ok">✓</span>
      )}
      {lastCompileMs != null && !busy && (
        <span className="tb-badge tb-badge-time" title="Last compile time">
          {lastCompileMs < 1000 ? `${lastCompileMs}ms` : `${(lastCompileMs/1000).toFixed(1)}s`}
        </span>
      )}
      {(isCompiling || isUploading) && (
        <div className="tb-task">
          <span className="spin">⟳</span>
          {isUploading ? 'Uploading…' : 'Compiling…'}
        </div>
      )}
      {autoVerify    && !busy && <span className="tb-badge" title="Auto-verify">AV</span>}
      {verboseOutput && !busy && <span className="tb-badge tb-badge-v" title="Verbose">V</span>}

      <div className="toolbar-divider" />

      <button className={`tb-btn tb-icon ${serialActive  ? 'active' : ''}`}
        title="Serial Monitor  Ctrl+Shift+M" onClick={onToggleSerial}>
        <MonitorIcon />
      </button>
      <button className={`tb-btn tb-icon ${plotterActive ? 'active' : ''}`}
        title="Serial Plotter  Ctrl+Shift+L" onClick={onTogglePlotter}>
        <PlotIcon />
      </button>

      <div className="tb-filename" title={fileName}>
        {fileName}{modified ? ' ●' : ''}
      </div>
    </div>
  );
}

function WifiIcon()     { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20" strokeWidth="3"/></svg>; }
function SidebarIcon()  { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>; }
function VerifyIcon()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>; }
function UploadIcon()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>; }
function StopIcon()     { return <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>; }
function GearIcon()     { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>; }
function MonitorIcon()  { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>; }
function PlotIcon()     { return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>; }
function TemplateIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>; }
