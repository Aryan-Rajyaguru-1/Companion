/**
 * monitor-utils.js
 * Mirrors the utility functions from arduino-ide-main:
 *   serial/monitor/monitor-utils.ts
 *
 * Handles incremental line accumulation, buffer truncation,
 * and clipboard export for the Serial Monitor output.
 */

const MAX_CHARS = 400_000;   // matches arduino-ide-main char cap
export const MAX_LINES = 3_000;

/**
 * Convert incoming raw message strings into line objects,
 * appending to the existing lines array.
 *
 * Handles:
 *  - \r\n  (Windows)
 *  - \n    (Unix)
 *  - \r    (old Mac)
 *  - Partial lines (no newline at end — buffered in the last entry)
 *
 * @param {string[]} messages     - new incoming message strings
 * @param {Line[]}   existingLines - current lines array
 * @param {number}   charCount    - current total char count
 * @returns {[Line[], number]} [newLines, newCharCount]
 */
export function messagesToLines(messages, existingLines, charCount) {
  let lines = [...existingLines];
  let count = charCount;

  for (const msg of messages) {
    count += msg.length;

    // Split on any combination of \r\n, \r, \n
    const parts = msg.split(/\r\n|\r|\n/);

    if (parts.length === 1) {
      // No newline — append to last incomplete line
      if (lines.length === 0 || lines[lines.length - 1].complete) {
        lines.push({ message: parts[0], complete: false, lineLen: parts[0].length });
      } else {
        const last = lines[lines.length - 1];
        lines[lines.length - 1] = {
          message: last.message + parts[0],
          complete: false,
          lineLen: last.lineLen + parts[0].length,
        };
      }
    } else {
      // First part appends to existing incomplete line (or starts new)
      if (lines.length > 0 && !lines[lines.length - 1].complete) {
        const last = lines[lines.length - 1];
        lines[lines.length - 1] = {
          message: last.message + parts[0],
          complete: true,
          lineLen: last.lineLen + parts[0].length,
        };
      } else {
        lines.push({ message: parts[0], complete: true, lineLen: parts[0].length });
      }

      // Middle parts are complete lines
      for (let i = 1; i < parts.length - 1; i++) {
        lines.push({ message: parts[i], complete: true, lineLen: parts[i].length });
      }

      // Last part: incomplete if message didn't end with newline
      const lastPart = parts[parts.length - 1];
      lines.push({ message: lastPart, complete: false, lineLen: lastPart.length });
    }
  }

  return [lines, count];
}

/**
 * Truncate the line buffer when total chars exceed MAX_CHARS.
 * Removes oldest lines. Mirrors truncateLines() in arduino-ide-main.
 *
 * @param {Line[]} lines
 * @param {number} charCount
 * @returns {[Line[], number]}
 */
export function truncateLines(lines, charCount) {
  if (charCount <= MAX_CHARS) return [lines, charCount];

  let excess = charCount - MAX_CHARS;
  let i = 0;
  while (i < lines.length && excess > 0) {
    excess -= lines[i].lineLen + 1; // +1 for the newline
    i++;
  }

  const truncated = lines.slice(i);
  const newCount  = truncated.reduce((acc, l) => acc + l.lineLen + 1, 0);
  return [truncated, newCount];
}

/**
 * Join lines back into a single string for clipboard copy.
 * Mirrors joinLines() in arduino-ide-main.
 *
 * @param {Line[]} lines
 * @returns {string}
 */
export function joinLines(lines) {
  return lines.map(l => l.message).join('\n');
}

/**
 * Format a Date as HH:MM:SS.mmm
 * @param {Date} date
 * @returns {string}
 */
export function formatTimestamp(date) {
  const h  = String(date.getHours()).padStart(2, '0');
  const m  = String(date.getMinutes()).padStart(2, '0');
  const s  = String(date.getSeconds()).padStart(2, '0');
  const ms = String(date.getMilliseconds()).padStart(3, '0');
  return `${h}:${m}:${s}.${ms}`;
}
