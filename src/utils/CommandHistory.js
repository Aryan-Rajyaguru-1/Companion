/**
 * CommandHistory
 * Mirrors the behaviour of CommandHistory.java from Arduino-master.
 * 
 * - Circular buffer of MAX_SIZE entries
 * - UP   → previous command (older)
 * - DOWN → next command (newer)
 * - ESC  → reset to current unexecuted draft
 */
export class CommandHistory {
  constructor(maxSize = 100) {
    this._max     = maxSize;
    this._history = [];        // oldest … newest
    this._cursor  = -1;        // -1 = not navigating
    this._draft   = '';        // the text typed before UP was pressed
  }

  /** Call when user submits a command. */
  addCommand(cmd) {
    if (!cmd.trim()) return;
    // De-duplicate consecutive identical entries
    if (this._history.length > 0 && this._history[this._history.length - 1] === cmd) {
      this._cursor = -1;
      this._draft  = '';
      return;
    }
    if (this._history.length >= this._max) {
      this._history.shift();
    }
    this._history.push(cmd);
    this._cursor = -1;
    this._draft  = '';
  }

  /** Returns true if there is a previous (older) command to navigate to. */
  hasPreviousCommand() {
    return this._history.length > 0 && this._cursor !== 0;
  }

  /** Returns true if there is a next (newer) command to navigate to. */
  hasNextCommand() {
    return this._cursor > 0;
  }

  /**
   * Move to the previous (older) command.
   * @param {string} currentText - the current input text (saved as draft on first UP)
   */
  getPreviousCommand(currentText) {
    if (this._history.length === 0) return currentText;
    if (this._cursor === -1) {
      this._draft  = currentText;
      this._cursor = this._history.length - 1;
    } else if (this._cursor > 0) {
      this._cursor--;
    }
    return this._history[this._cursor];
  }

  /** Move to the next (newer) command. */
  getNextCommand() {
    if (this._cursor === -1) return this._draft;
    this._cursor++;
    if (this._cursor >= this._history.length) {
      this._cursor = -1;
      return this._draft;
    }
    return this._history[this._cursor];
  }

  /**
   * ESC: reset cursor and restore the draft.
   * Returns the draft text that was being typed.
   */
  resetHistoryLocation() {
    this._cursor = -1;
    return this._draft;
  }

  /** True when actively navigating history. */
  isNavigating() {
    return this._cursor !== -1;
  }

  /** Number of stored commands. */
  get size() { return this._history.length; }
}
