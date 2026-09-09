/**
 * UploadProgress.jsx  (#5)
 * Floating overlay showing compile + upload progress with:
 *   - Animated progress bar
 *   - Stage pipeline with pulsing active dot
 *   - Stage label that updates as output arrives
 *   - Smooth percentage transitions
 */

import { useEffect, useState, useRef } from 'react';
import './UploadProgress.css';

// ── Stage definitions ──────────────────────────────────────────
const COMPILE_STAGES = [
  { key: 'resolve',    label: 'Resolving board…'      },
  { key: 'preprocess', label: 'Preprocessing sketch…' },
  { key: 'core',       label: 'Building core…'         },
  { key: 'libraries',  label: 'Building libraries…'    },
  { key: 'sketch',     label: 'Compiling sketch…'      },
  { key: 'link',       label: 'Linking…'               },
  { key: 'extract',    label: 'Extracting binary…'     },
];

const UPLOAD_STAGES = [
  { key: 'bootloader', label: 'Entering bootloader…'  },
  { key: 'erase',      label: 'Erasing flash…'         },
  { key: 'write',      label: 'Writing firmware…'      },
  { key: 'verify',     label: 'Verifying…'             },
  { key: 'reset',      label: 'Resetting device…'      },
];

// ── Keyword → stage detection ──────────────────────────────────
const STAGE_PATTERNS = [
  // Upload stages checked first (most specific)
  { key: 'reset',      phase: 'upload',   patterns: ['upload complete', 'resetting', 'reset'] },
  { key: 'verify',     phase: 'upload',   patterns: ['verif'] },
  { key: 'write',      phase: 'upload',   patterns: ['writing'] },
  { key: 'erase',      phase: 'upload',   patterns: ['erase'] },
  { key: 'bootloader', phase: 'upload',   patterns: ['bootloader', 'entering', 'uploading'] },
  // Compile stages
  { key: 'extract',    phase: 'compile',  patterns: ['extract', 'objcopy'] },
  { key: 'link',       phase: 'compile',  patterns: ['link'] },
  { key: 'sketch',     phase: 'compile',  patterns: ['compil'] },
  { key: 'libraries',  phase: 'compile',  patterns: ['librar'] },
  { key: 'core',       phase: 'compile',  patterns: ['core', 'building core'] },
  { key: 'preprocess', phase: 'compile',  patterns: ['preprocess'] },
  { key: 'resolve',    phase: 'compile',  patterns: ['resolv', 'board'] },
];

function detectStage(lines) {
  const last15 = lines.slice(-15).map(l => (l.text || '').toLowerCase());
  const joined = last15.join(' ');

  for (const { key, phase, patterns } of STAGE_PATTERNS) {
    if (patterns.some(p => joined.includes(p))) {
      return { key, phase };
    }
  }
  return null;
}

function stageLabel(stageKey, allStages) {
  return allStages.find(s => s.key === stageKey)?.label || null;
}

// ── Component ─────────────────────────────────────────────────
export default function UploadProgress({ isCompiling, isUploading, consoleLogs, onCancel }) {
  const [currentStage, setCurrentStage] = useState(null);
  const [displayPct,   setDisplayPct]   = useState(0);
  const animFrameRef   = useRef(null);
  const targetPctRef   = useRef(0);
  const currentPctRef  = useRef(0);

  const allStages = isUploading
    ? [...COMPILE_STAGES, ...UPLOAD_STAGES]
    : COMPILE_STAGES;

  // ── Detect stage from console output ────────────────────────
  useEffect(() => {
    if (!isCompiling && !isUploading) {
      setCurrentStage(null);
      targetPctRef.current = 0;
      return;
    }
    const detected = detectStage(consoleLogs);
    if (detected) {
      setCurrentStage(detected);
      const idx = allStages.findIndex(s => s.key === detected.key);
      if (idx >= 0) {
        targetPctRef.current = Math.round((idx + 1) * 100 / allStages.length);
      }
    }
  }, [consoleLogs, isCompiling, isUploading]);

  // ── Smooth progress animation ────────────────────────────────
  useEffect(() => {
    if (!isCompiling && !isUploading) {
      currentPctRef.current = 0;
      setDisplayPct(0);
      return;
    }

    const animate = () => {
      const target  = targetPctRef.current;
      const current = currentPctRef.current;
      if (Math.abs(target - current) < 0.5) {
        currentPctRef.current = target;
        setDisplayPct(Math.round(target));
      } else {
        const next = current + (target - current) * 0.08;
        currentPctRef.current = next;
        setDisplayPct(Math.round(next));
        animFrameRef.current = requestAnimationFrame(animate);
      }
    };
    animFrameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [isCompiling, isUploading, currentStage]);

  if (!isCompiling && !isUploading) return null;

  const label = currentStage
    ? stageLabel(currentStage.key, allStages)
    : (isUploading ? 'Uploading wirelessly…' : 'Compiling…');

  const currentIdx = currentStage
    ? allStages.findIndex(s => s.key === currentStage.key)
    : -1;

  return (
    <div className="upload-progress-overlay">
      <div className="up-card">
        {/* Title */}
        <div className="up-title">
          <span className="spin">⟳</span>
          {isUploading ? 'Wireless Upload' : 'Compiling Sketch'}
        </div>

        {/* Stage label */}
        <div className="up-stage-label">{label}</div>

        {/* Progress bar */}
        <div className="up-bar-track">
          <div
            className="up-bar-fill"
            style={{ width: `${Math.max(3, displayPct)}%` }}
          />
        </div>

        {/* Percentage */}
        <div className="up-pct">{displayPct}%</div>

        {/* Stage pipeline dots */}
        <div className="up-stages">
          {allStages.map((s, i) => {
            const isDone   = i < currentIdx;
            const isActive = i === currentIdx;
            return (
              <span
                key={s.key}
                className={`up-dot ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
                title={s.label}
              />
            );
          })}
        </div>

        {/* Cancel button */}
        {onCancel && (
          <button className="btn up-cancel" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
