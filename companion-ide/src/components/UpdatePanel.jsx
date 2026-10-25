/**
 * UpdatePanel.jsx
 *
 * Status and actions for the two separately released pieces of software:
 *   - Companion CLI: checked and installed by `companion self-update`.
 *   - Companion IDE: checked from the same release metadata, but installed by
 *     opening the published platform installer. The IDE does not replace its
 *     own running bundle.
 *
 * All release data comes from the main process. The renderer never supplies or
 * opens URLs itself.
 */

import './UpdatePanel.css';

function displayVersion(value) {
  const text = String(value || '').trim();
  if (!text) return 'unknown';
  return /^v/i.test(text) ? text : `v${text}`;
}

function checkedLabel(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return `Last checked ${date.toLocaleString()}`;
}

function StatusPill({ state }) {
  const labels = {
    current: 'Up to date',
    available: 'Update available',
    unknown: 'Unknown',
  };
  return <span className={`up-pill up-pill-${state}`}>{labels[state] || labels.unknown}</span>;
}

function UpdateIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
    </svg>
  );
}

export default function UpdatePanel({
  status,
  checking = false,
  applying = false,
  error = '',
  message = '',
  onCheck,
  onApplyCli,
  onOpenIdeInstaller,
  onOpenRelease,
  onClose,
}) {
  const cli = status?.success ? status.cli : null;
  const ide = status?.success ? status.ide : null;
  const anyUpdate = !!(cli?.updateAvailable || ide?.updateAvailable);
  const checked = checkedLabel(status?.checkedAt);
  const platform = status?.platform
    ? `${status.platform}${status.architecture ? ` ${status.architecture}` : ''}`
    : '';
  const overallState = checking && !status
    ? 'unknown'
    : anyUpdate ? 'available' : status?.success ? 'current' : 'unknown';

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose?.()}>
      <div className="modal up-modal" role="dialog" aria-modal="true"
        aria-labelledby="up-title" onClick={e => e.stopPropagation()}>

        <div className="modal-header">
          <span className="modal-title" id="up-title"><UpdateIcon /> Software Updates</span>
          <button className="modal-close" onClick={onClose} aria-label="Close updates">✕</button>
        </div>

        <div className="up-body">
          <div className="up-top">
            <div className="up-top-status">
              <StatusPill state={overallState} />
              {checked && <span className="up-checked">{checked}</span>}
            </div>
            <button className="btn up-check" onClick={onCheck} disabled={checking || applying}>
              {checking ? <><span className="spin">⟳</span> Checking…</> : 'Check again'}
            </button>
          </div>

          {error && <div className="up-alert up-alert-error" role="alert">{error}</div>}
          {message && <div className="up-alert up-alert-info" role="status">{message}</div>}

          {!status && checking && (
            <div className="up-empty"><span className="spin">⟳</span> Checking the release channel…</div>
          )}

          {!status && !checking && (
            <div className="up-empty">
              Update status is unavailable. Check again to retry.
            </div>
          )}

          {status && !status.success && (
            <div className="up-empty">
              The release channel could not be read. Check again, or open the release page.
            </div>
          )}

          {status?.success && (
            <>
              <section className={`up-card ${cli?.updateAvailable ? 'has-update' : ''}`}>
                <div className="up-card-head">
                  <div>
                    <h3>Companion CLI</h3>
                    <p>Compiler, uploader, and release metadata service.</p>
                  </div>
                  <StatusPill state={cli?.updateAvailable ? 'available' : 'current'} />
                </div>

                <div className="up-versions">
                  <div className="up-version">
                    <span>Installed</span>
                    <strong>{displayVersion(cli?.currentVersion)}</strong>
                  </div>
                  <div className="up-version-arrow" aria-hidden="true">→</div>
                  <div className="up-version">
                    <span>Latest verified</span>
                    <strong>{displayVersion(cli?.latestVersion)}</strong>
                  </div>
                </div>

                {cli?.updateAvailable ? (
                  <>
                    <div className="up-actions">
                      <button className="btn primary" onClick={onApplyCli} disabled={applying || checking}>
                        {applying
                          ? <><span className="spin">⟳</span> Downloading and verifying…</>
                          : `Update CLI to ${displayVersion(cli.latestVersion)}`}
                      </button>
                    </div>
                    <p className="up-hint">
                      The download is staged beside <code>~/.companion-cli/bin/companion</code> and
                      its SHA-256 is verified against <code>SHA256SUMS.txt</code> before the old
                      binary is replaced. The local daemon is restarted if it was running.
                    </p>
                  </>
                ) : (
                  <p className="up-current">Companion CLI is up to date.</p>
                )}
              </section>

              <section className={`up-card ${ide?.updateAvailable ? 'has-update' : ''}`}>
                <div className="up-card-head">
                  <div>
                    <h3>Companion IDE</h3>
                    <p>Editor, serial tools, and board management.</p>
                  </div>
                  <StatusPill state={ide?.updateAvailable ? 'available' : 'current'} />
                </div>

                <div className="up-versions">
                  <div className="up-version">
                    <span>Installed</span>
                    <strong>{displayVersion(ide?.currentVersion)}</strong>
                  </div>
                  <div className="up-version-arrow" aria-hidden="true">→</div>
                  <div className="up-version">
                    <span>Latest published</span>
                    <strong>{displayVersion(ide?.latestVersion)}</strong>
                  </div>
                </div>

                {ide?.updateAvailable ? (
                  <>
                    <div className="up-actions">
                      {ide.installer ? (
                        <button className="btn primary" onClick={onOpenIdeInstaller}>
                          Download {displayVersion(ide.latestVersion)} installer
                        </button>
                      ) : (
                        <button className="btn primary" onClick={onOpenRelease}>
                          Open release page
                        </button>
                      )}
                    </div>
                    <p className="up-hint">
                      {ide.installer
                        ? `This opens the published ${ide.installer.name} download for ${platform || 'this computer'}. Close the IDE before installing the replacement.`
                        : `No IDE installer was published for ${platform || 'this platform/architecture'}. The release page lists every available download.`}
                    </p>
                  </>
                ) : (
                  <p className="up-current">Companion IDE is up to date.</p>
                )}
              </section>

              <div className="up-footer">
                <button className="btn" onClick={onOpenRelease} disabled={!status.releaseUrl && !ide?.releaseUrl}>
                  Release page
                </button>
                <button className="btn" onClick={onClose}>Close</button>
              </div>

              {status.releaseNotes && (
                <details className="up-notes">
                  <summary>Release notes{status.releaseName ? ` — ${status.releaseName}` : ''}</summary>
                  <pre>{status.releaseNotes}</pre>
                </details>
              )}
            </>
          )}

          <p className="up-policy">
            The IDE never installs itself silently. Update checks and CLI installation use the
            bundled Companion CLI; IDE installers are downloaded and opened by you.
          </p>
        </div>
      </div>
    </div>
  );
}
