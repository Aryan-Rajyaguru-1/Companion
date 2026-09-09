/**
 * AutoCorrectPanel.jsx
 * Shows after a failed compile:
 *   - List of detected fixable errors
 *   - Diff preview (before → after for each fix)
 *   - "Copy Errors" button
 *   - "Auto Correct" button (applies all fixes)
 *   - Individual per-fix toggle to cherry-pick
 */

import { useState, useMemo } from 'react';
import { AutoCorrector, errorsToText } from '../utils/auto-correct';
import './AutoCorrectPanel.css';

export default function AutoCorrectPanel({
  sourceCode,
  compileErrors,
  filePath,
  onApply,     // (newCode: string, summary: string) => void
  onDismiss,   // () => void
}) {
  const [copied,       setCopied]       = useState(false);
  const [applying,     setApplying]     = useState(false);
  const [expandedFix,  setExpandedFix]  = useState(null);
  const [disabledFixes, setDisabledFixes] = useState(new Set());
  const [applied,      setApplied]      = useState(false);

  // Build corrector once per (sourceCode, errors)
  const corrector = useMemo(() => {
    const c = new AutoCorrector(sourceCode, compileErrors, filePath);
    c.analyze();
    return c;
  }, [sourceCode, compileErrors, filePath]);

  const allFixes  = corrector.fixes;
  const canFix    = allFixes.length > 0;
  const { hunks } = corrector.preview();

  // ── Copy errors to clipboard ────────────────────────────────
  const handleCopy = () => {
    const text = errorsToText(compileErrors);
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  // ── Apply selected fixes ────────────────────────────────────
  const handleApply = () => {
    if (!canFix || applied) return;
    setApplying(true);

    // Build a fresh corrector with only enabled fixes
    const activeFixes = allFixes.filter((_, i) => !disabledFixes.has(i));
    if (activeFixes.length === 0) { setApplying(false); return; }

    // Re-run apply with only selected fixes
    const lines = sourceCode.split('\n');
    const sorted = [...activeFixes].sort((a, b) => b.fix.lineIndex - a.fix.lineIndex);
    for (const { fix } of sorted) {
      const li = fix.lineIndex;
      if (li < 0 || li > lines.length) continue;
      if (fix.insertBefore != null && fix.newLine === null) {
        lines.splice(li, 0, fix.insertBefore);
      } else if (fix.insertBefore != null && fix.newLine !== null) {
        lines[li] = fix.newLine;
        lines.splice(li, 0, fix.insertBefore);
      } else if (fix.newLine !== null) {
        lines[li] = fix.newLine;
      }
    }

    const newCode = lines.join('\n');
    const summary = activeFixes.map(f => `• ${f.fix.description}`).join('\n');

    setTimeout(() => {
      setApplying(false);
      setApplied(true);
      onApply(newCode, summary);
    }, 200);
  };

  const toggleFix = (i) => {
    setDisabledFixes(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  const activeCount = allFixes.length - disabledFixes.size;

  return (
    <div className="ac-panel">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="ac-header">
        <div className="ac-title">
          <ErrorIcon />
          <span>
            {compileErrors.length} error{compileErrors.length !== 1 ? 's' : ''}
            {canFix && (
              <span className="ac-fixable-badge">
                {allFixes.length} auto-fixable
              </span>
            )}
          </span>
        </div>

        <div className="ac-actions">
          {/* Copy errors */}
          <button className="btn ac-btn" onClick={handleCopy} title="Copy all errors to clipboard">
            {copied ? <><CheckIcon /> Copied!</> : <><CopyIcon /> Copy Errors</>}
          </button>

          {/* Auto correct */}
          {canFix && !applied && (
            <button
              className="btn primary ac-btn ac-fix-btn"
              onClick={handleApply}
              disabled={applying || activeCount === 0}
              title={`Apply ${activeCount} auto-fix${activeCount !== 1 ? 'es' : ''}`}
            >
              {applying
                ? <><span className="spin">⟳</span> Applying…</>
                : <><WandIcon /> Auto Correct ({activeCount})</>}
            </button>
          )}

          {applied && (
            <span className="ac-applied-badge">
              <CheckIcon /> Applied — press Compile to verify
            </span>
          )}

          <button className="btn ac-btn ac-dismiss" onClick={onDismiss} title="Dismiss">✕</button>
        </div>
      </div>

      {/* ── Fix list ─────────────────────────────────────────── */}
      {canFix && !applied && (
        <div className="ac-fix-list">
          <div className="ac-fix-list-label">
            Detected fixes — uncheck to skip individual ones:
          </div>
          {allFixes.map(({ fix, error }, i) => {
            const enabled  = !disabledFixes.has(i);
            const expanded = expandedFix === i;
            const hunk     = hunks[i];

            return (
              <div
                key={i}
                className={`ac-fix-item ${enabled ? '' : 'disabled'}`}
              >
                <label className="ac-fix-checkbox">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggleFix(i)}
                  />
                </label>

                <div className="ac-fix-body">
                  <div
                    className="ac-fix-desc"
                    onClick={() => setExpandedFix(expanded ? null : i)}
                  >
                    <span className="ac-fix-rule-badge">{fix.ruleId}</span>
                    <span className="ac-fix-text">{fix.description}</span>
                    <span className="ac-fix-line">line {fix.lineIndex + 1}</span>
                    <span className="ac-expand-btn">{expanded ? '▲' : '▼'}</span>
                  </div>

                  {/* Diff preview */}
                  {expanded && hunk && (
                    <div className="ac-diff">
                      {hunk.before !== '(insert)' && (
                        <div className="ac-diff-line ac-diff-del">
                          <span className="ac-diff-gutter">−</span>
                          <code>{hunk.before}</code>
                        </div>
                      )}
                      <div className="ac-diff-line ac-diff-add">
                        <span className="ac-diff-gutter">+</span>
                        <code>{hunk.after}</code>
                      </div>
                    </div>
                  )}

                  <div className="ac-fix-error-ref">
                    from: <em>{error.message.slice(0, 80)}{error.message.length > 80 ? '…' : ''}</em>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── No fixes available ───────────────────────────────── */}
      {!canFix && (
        <div className="ac-no-fix">
          <InfoIcon />
          <span>
            No automatic fix available for these errors.
            Complex errors require manual correction.
          </span>
        </div>
      )}
    </div>
  );
}

// ── Icons ────────────────────────────────────────────────────────
function ErrorIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>;
}
function CopyIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>;
}
function CheckIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="20 6 9 17 4 12"/></svg>;
}
function WandIcon() {
  return <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 4V2M15 16v-2M8 9h2M20 9h2M17.8 11.8L19 13M17.8 6.2L19 5M3 21l9-9M12.2 6.2L11 5"/></svg>;
}
function InfoIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>;
}
