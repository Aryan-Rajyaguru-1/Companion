/**
 * FlashUsageBar.jsx
 * Displays flash storage and RAM usage after a successful compile.
 * Mirrors Arduino IDE's post-compile memory usage report exactly.
 *
 * Shows:
 *   Program Storage:  ████████░░░░  14,832 / 253,952 bytes  (4%)
 *   Dynamic Memory:   ██░░░░░░░░░░   2,172 /   8,192 bytes  (6%)
 *
 * Bar colour: teal < 75%, yellow 75–90%, red ≥ 90% (same thresholds as Arduino IDE)
 */

import { usageSeverity, formatBytes } from '../utils/flash-parser';
import './FlashUsageBar.css';

export default function FlashUsageBar({ flash, ram }) {
  if (!flash && !ram) return null;

  return (
    <div className="flash-usage-bar">
      {flash && (
        <UsageRow
          label="Program Storage"
          icon="⚙"
          used={flash.used}
          maximum={flash.maximum}
          pct={flash.pct}
        />
      )}
      {ram && (
        <UsageRow
          label="Dynamic Memory"
          icon="◫"
          used={ram.used}
          maximum={ram.maximum}
          pct={ram.pct}
        />
      )}
    </div>
  );
}

function UsageRow({ label, icon, used, maximum, pct }) {
  const sev = usageSeverity(pct);
  return (
    <div className="fub-row">
      <span className="fub-icon">{icon}</span>
      <span className="fub-label">{label}</span>
      <div className="fub-track">
        <div
          className={`fub-fill ${sev}`}
          style={{ width: `${Math.min(100, pct)}%` }}
          title={`${pct}% used`}
        />
      </div>
      <span className={`fub-pct ${sev}`}>{pct}%</span>
      <span className="fub-detail">
        {formatBytes(used)} / {formatBytes(maximum)}
      </span>
    </div>
  );
}
