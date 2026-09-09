/**
 * recent-files.js
 * Manages a list of recently opened sketch files, persisted to localStorage.
 * Max 10 entries. Most recently opened appears first.
 */

const KEY      = 'companion.recentFiles';
const MAX_SIZE = 10;

export function getRecentFiles() {
  try {
    const stored = localStorage.getItem(KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Add (or move to top) a file path.
 * @param {string} filePath
 * @param {string} [name]
 */
export function addRecentFile(filePath, name) {
  if (!filePath) return;
  const entries = getRecentFiles().filter(e => e.path !== filePath);
  const entry = {
    path:    filePath,
    name:    name || filePath.split(/[/\\]/).pop(),
    openedAt: new Date().toISOString(),
  };
  const next = [entry, ...entries].slice(0, MAX_SIZE);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {}
}

/**
 * Remove a file path from recents.
 */
export function removeRecentFile(filePath) {
  const next = getRecentFiles().filter(e => e.path !== filePath);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {}
}

export function clearRecentFiles() {
  try { localStorage.removeItem(KEY); } catch {}
}
