/**
 * CompileProgress.jsx
 * Bug fix #5: Receives consoleLogs (reactive state array) instead of
 * rawOutputRef.current (mutable ref that never triggers re-render).
 * Now actually updates stage + file display during compilation.
 */
import { useMemo } from 'react';
import './CompileProgress.css';

const STAGES = [
  { key: 'init',    label: 'Initialising',      patterns: ['resolv','board','fqbn','init','platform'] },
  { key: 'preproc', label: 'Preprocessing',      patterns: ['preprocess','ctags','sketch'] },
  { key: 'core',    label: 'Building core',      patterns: ['building core','compiling core','libcore','core.a'] },
  { key: 'libs',    label: 'Building libraries', patterns: ['librar','building lib'] },
  { key: 'sketch',  label: 'Compiling sketch',   patterns: ['compiling sketch','.ino.cpp','.ino'] },
  { key: 'link',    label: 'Linking',            patterns: ['link','.elf','ld '] },
  { key: 'extract', label: 'Extracting binary',  patterns: ['objcopy','.bin','.hex','extract','esptool'] },
];

const FILE_RE = /(?:Compiling|Building)\s+.*?([^/\\]+\.(?:ino|cpp|c|h|s))/i;

function detectStage(logLines) {
  if (!logLines?.length) return null;
  // Scan last 20 lines for stage keyword
  const recent = logLines.slice(-20).map(l => (l.text || '').toLowerCase()).join(' ');
  for (let i = STAGES.length - 1; i >= 0; i--) {
    if (STAGES[i].patterns.some(p => recent.includes(p))) return STAGES[i];
  }
  return STAGES[0];
}

function detectCurrentFile(logLines) {
  if (!logLines?.length) return null;
  for (let i = logLines.length - 1; i >= Math.max(0, logLines.length - 10); i--) {
    const m = FILE_RE.exec(logLines[i]?.text || '');
    if (m) return m[1];
  }
  return null;
}

export default function CompileProgress({ isCompiling, consoleLogs }) {
  // BUG 5 FIX: consoleLogs is React state — re-renders fire on every new log line
  const stage       = useMemo(() => detectStage(consoleLogs),       [consoleLogs]);
  const currentFile = useMemo(() => detectCurrentFile(consoleLogs), [consoleLogs]);

  const stageIdx = stage ? STAGES.findIndex(s => s.key === stage.key) : 0;
  const pct      = Math.max(5, Math.round(((stageIdx + 0.5) / STAGES.length) * 100));

  if (!isCompiling) return null;

  return (
    <div className="compile-progress">
      <div className="cp-header">
        <span className="cp-spin">⟳</span>
        <span className="cp-stage">{stage?.label ?? 'Compiling…'}</span>
        {currentFile && <span className="cp-file" title={currentFile}>{currentFile}</span>}
        <span className="cp-pct">{pct}%</span>
      </div>
      <div className="cp-bar-track">
        <div className="cp-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="cp-dots">
        {STAGES.map((s, i) => (
          <span key={s.key}
            className={`cp-dot ${i < stageIdx ? 'done' : ''} ${i === stageIdx ? 'active' : ''}`}
            title={s.label} />
        ))}
      </div>
    </div>
  );
}
