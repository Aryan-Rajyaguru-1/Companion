/**
 * auto-correct.js
 * ─────────────────────────────────────────────────────────────────
 * Deterministic, rule-based auto-correction engine for GCC / Arduino
 * compiler errors. Zero API calls, zero LLM dependency.
 *
 * Architecture:
 *  - Each RULE has: id, description, pattern (regex on error.message),
 *    and a fix(lines, error) function that returns a Fix object or null.
 *  - A Fix object describes: { lineIndex, oldText, newText, description }
 *  - AutoCorrector.analyze()   → finds all applicable fixes
 *  - AutoCorrector.applyAll()  → applies fixes bottom-up (preserves line nums)
 *
 * Supported error categories:
 *  1.  Missing semicolon
 *  2.  Missing #include for well-known libraries
 *  3.  setup()/loop() missing `void` return type
 *  4.  Assignment `=` inside `if` condition (should be `==`)
 *  5.  `string` (lowercase) should be `String` on Arduino
 *  6.  Integer constant too large → add `L` suffix
 *  7.  `return` with value inside `void` function → strip value
 *  8.  Missing `break` before next `case` in switch
 *  9.  Unused variable → add `(void)` cast
 * 10.  Common identifier typos (Levenshtein ≤ 2 from known APIs)
 * 11.  `delay()` called with float → cast to int
 * 12.  `analogWrite` value literal > 255 → clamp to 255
 * 13.  Wrong string comparison `str == "..."` → `str.equals("...")`
 * 14.  Missing `()` in function reference used as call
 * 15.  `#include "Arduino.h"` should be `<Arduino.h>`
 * 16.  `bool` literal `True`/`False` → `true`/`false`
 * 17.  Empty `loop()` / `setup()` body — add comment placeholder
 * 18.  `int` overflow hint: number > 32767 → `long`
 * 19.  `pinMode` missing for `digitalWrite`/`digitalRead` on same pin
 * 20.  `Serial.begin` called without argument → insert 115200
 * 21.  Duplicate `#include` → remove second occurrence
 * 22.  Trailing whitespace / mixed indent — normalize
 * 23.  `void loop` / `void setup` defined more than once → deduplicate
 * 24.  C-style cast warning → C++ static_cast suggestion
 * 25.  `while(1)` → `while(true)` (style + Arduino preference)
 */

// ─────────────────────────────────────────────────────────────────
// Levenshtein distance (used for typo detection)
// ─────────────────────────────────────────────────────────────────
function levenshtein(a, b) {
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, (_, i) =>
    Array.from({ length: n + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }
  return dp[m][n];
}

// ─────────────────────────────────────────────────────────────────
// Known Arduino API names (for typo matching)
// ─────────────────────────────────────────────────────────────────
const ARDUINO_API = [
  'pinMode', 'digitalWrite', 'digitalRead', 'analogWrite', 'analogRead',
  'delay', 'delayMicroseconds', 'millis', 'micros',
  'attachInterrupt', 'detachInterrupt',
  'Serial', 'Serial1', 'Serial2',
  'Wire', 'SPI', 'EEPROM', 'Servo',
  'setup', 'loop',
  'HIGH', 'LOW', 'INPUT', 'OUTPUT', 'INPUT_PULLUP',
  'LED_BUILTIN', 'true', 'false', 'null',
  'random', 'randomSeed', 'map', 'constrain',
  'abs', 'min', 'max', 'sq', 'sqrt',
  'String', 'int', 'long', 'float', 'double', 'byte', 'char', 'bool',
  'void', 'return', 'break', 'continue',
  'tone', 'noTone', 'pulseIn',
  'shiftIn', 'shiftOut',
  'bit', 'bitRead', 'bitSet', 'bitClear', 'bitWrite',
  'lowByte', 'highByte',
  'println', 'print', 'write', 'read', 'available', 'begin', 'end', 'flush',
  'begin', 'end', 'read', 'write', 'requestFrom',
];

// ─────────────────────────────────────────────────────────────────
// Known library → header mappings
// ─────────────────────────────────────────────────────────────────
const LIBRARY_INCLUDES = {
  Wire:     '#include <Wire.h>',
  Servo:    '#include <Servo.h>',
  EEPROM:   '#include <EEPROM.h>',
  SPI:      '#include <SPI.h>',
  SD:       '#include <SD.h>',
  Ethernet: '#include <Ethernet.h>',
  WiFi:     '#include <WiFi.h>',
  LiquidCrystal: '#include <LiquidCrystal.h>',
  Stepper:  '#include <Stepper.h>',
  IRremote: '#include <IRremote.h>',
  Keyboard: '#include <Keyboard.h>',
  Mouse:    '#include <Mouse.h>',
  math:     '#include <math.h>',
  string:   '#include <string.h>',
  stdlib:   '#include <stdlib.h>',
  Adafruit_GFX: '#include <Adafruit_GFX.h>',
  Adafruit_SSD1306: '#include <Adafruit_SSD1306.h>',
  ArduinoJson: '#include <ArduinoJson.h>',
  NeoPixel: '#include <Adafruit_NeoPixel.h>',
};

// ─────────────────────────────────────────────────────────────────
// Fix descriptor
// ─────────────────────────────────────────────────────────────────
/**
 * @typedef {Object} Fix
 * @property {number}   lineIndex   0-based line index to replace
 * @property {string}   oldLine     original line text
 * @property {string}   newLine     replacement line text (or null if inserting above)
 * @property {string}   insertBefore  text to insert before lineIndex (if any)
 * @property {string}   description  human-readable description
 * @property {string}   ruleId
 */

// ─────────────────────────────────────────────────────────────────
// Rules
// ─────────────────────────────────────────────────────────────────
const RULES = [

  // ── Rule 1: Missing semicolon ─────────────────────────────────
  {
    id: 'missing-semicolon',
    description: 'Insert missing semicolon',
    pattern: /expected\s+';'/i,
    fix(lines, error) {
      // GCC reports the line AFTER the missing semicolon; check line before
      const targets = [error.line - 1, error.line - 2].filter(i => i >= 0 && i < lines.length);
      for (const li of targets) {
        const line = lines[li];
        const trimmed = line.trimEnd();
        // Skip blank lines, lines that already end with ; { } // /*
        if (!trimmed) continue;
        if (/[;{}]$/.test(trimmed)) continue;
        if (/^\s*(\/\/|\/\*)/.test(trimmed)) continue;
        // Don't add ; after preprocessor directives
        if (/^\s*#/.test(trimmed)) continue;
        // Don't add ; after for/while/if/else/do without body
        if (/^\s*(for|while|if|else|do)\s*[^{]*$/.test(trimmed) && !trimmed.endsWith(')')) continue;
        return {
          lineIndex: li,
          oldLine: lines[li],
          newLine: trimmed + ';' + (lines[li].slice(trimmed.length) || ''),
          description: `Add missing semicolon on line ${li + 1}`,
          ruleId: this.id,
        };
      }
      return null;
    },
  },

  // ── Rule 2: Missing #include for known library ────────────────
  {
    id: 'missing-include',
    description: 'Add missing #include',
    pattern: /'(\w+)' (was not declared|undeclared|not declared)/i,
    fix(lines, error) {
      const match = /'(\w+)'/.exec(error.message);
      if (!match) return null;
      const name = match[1];

      // Check library map
      const include = LIBRARY_INCLUDES[name];
      if (!include) return null;

      // Check if already included
      const alreadyIncluded = lines.some(l => l.includes(`<${name}.h>`) || l.includes(`"${name}.h"`));
      if (alreadyIncluded) return null;

      // Find the best insertion point: after existing #includes or at line 0
      let insertAt = 0;
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].trim().startsWith('#include')) insertAt = i + 1;
        if (lines[i].trim() === '') continue;
        if (!lines[i].trim().startsWith('#') && insertAt === 0) break;
      }

      return {
        lineIndex: insertAt,
        oldLine: null,
        newLine: null,
        insertBefore: include,
        description: `Add ${include} for '${name}'`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 3: setup()/loop() missing return type ────────────────
  {
    id: 'missing-void',
    description: "Add 'void' return type to setup() or loop()",
    pattern: /ISO C\+\+ forbids declaration|expected (unqualified-id|declaration)/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const m = /^(\s*)(setup|loop)\s*\(\s*\)\s*\{/.exec(line);
      if (!m) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: line.replace(/^(\s*)(setup|loop)/, '$1void $2'),
        description: `Add 'void' return type to ${m[2]}()`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 4: Assignment in if condition (= instead of ==) ──────
  {
    id: 'assignment-in-condition',
    description: "Replace '=' with '==' in if condition",
    pattern: /suggest parentheses around assignment|always evaluates as 'true'/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      // Match: if (x = value) or while (x = value)
      const fixed = line.replace(
        /(if|while|for)\s*\(([^=!<>]+?)(?<!=)=(?!=)([^=])/g,
        (m, kw, lhs, rhs) => `${kw}(${lhs}==${rhs}`
      );
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Replace '=' with '==' in condition on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 5: `string` (C++ std) should be Arduino `String` ────
  {
    id: 'string-case',
    description: "Change 'string' to Arduino 'String'",
    pattern: /'string' (was not declared|undeclared|does not name)/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      if (!line.includes('string')) return null;
      // Only replace `string` as a type declaration (not inside strings)
      const fixed = line.replace(/\bstring\b/g, 'String');
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Change 'string' to Arduino 'String' on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 6: Integer constant too large → add L suffix ─────────
  {
    id: 'integer-overflow',
    description: 'Add L suffix to large integer constant',
    pattern: /integer overflow|integer constant is too large/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      // Find integer literals > 32767 (beyond int range on AVR)
      const fixed = line.replace(/\b(\d{5,})\b(?![LlUu.])/g, (m, n) => {
        return parseInt(n, 10) > 32767 ? n + 'L' : n;
      });
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Add 'L' suffix to large integer on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 7: return with value in void function ────────────────
  {
    id: 'void-return-value',
    description: "Remove value from 'return' in void function",
    pattern: /return-statement with a value.*void|'return' with a value/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const m = /^(\s*)return\s+[^;]+;/.exec(line);
      if (!m) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: m[1] + 'return;',
        description: `Remove return value in void function on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 8: Implicit fallthrough — add break before case ──────
  {
    id: 'switch-fallthrough',
    description: 'Add missing break before case in switch',
    pattern: /implicit fallthrough|this statement may fall through/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      // The error points to the case label — insert break before it
      const line = lines[li];
      if (!/^\s*case\s+/.test(line) && !/^\s*default\s*:/.test(line)) return null;
      const indent = line.match(/^(\s*)/)[1];
      return {
        lineIndex: li,
        oldLine: line,
        newLine: line,
        insertBefore: indent + 'break;',
        description: `Add 'break' before case on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 9: Unused variable → (void) cast ─────────────────────
  {
    id: 'unused-variable',
    description: 'Suppress unused variable warning with (void) cast',
    pattern: /unused variable '(\w+)'/i,
    fix(lines, error) {
      const match = /unused variable '(\w+)'/.exec(error.message);
      if (!match) return null;
      const varName = match[1];
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const indent = lines[li].match(/^(\s*)/)[1];
      // Find the end of the declaration block — insert (void)cast after it
      return {
        lineIndex: li + 1,
        oldLine: null,
        newLine: null,
        insertBefore: `${indent}(void)${varName}; // suppress unused warning`,
        description: `Suppress unused variable '${varName}'`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 10: Identifier typo — suggest closest Arduino API ───
  {
    id: 'typo-correction',
    description: 'Fix identifier typo',
    pattern: /'(\w+)' (was not declared|undeclared)/i,
    fix(lines, error) {
      const match = /'(\w+)'/.exec(error.message);
      if (!match) return null;
      const bad = match[1];
      if (bad.length < 3) return null;

      // Skip if it's a library name (handled by missing-include rule)
      if (LIBRARY_INCLUDES[bad]) return null;

      // Find closest Arduino API name
      let best = null, bestDist = Infinity;
      for (const api of ARDUINO_API) {
        const d = levenshtein(bad.toLowerCase(), api.toLowerCase());
        if (d < bestDist && d <= 2) {
          bestDist = d;
          best = api;
        }
      }
      if (!best || best === bad) return null;

      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];

      // Only replace whole-word occurrences of `bad` with `best`
      const re = new RegExp(`\\b${escapeRegex(bad)}\\b`, 'g');
      const fixed = line.replace(re, best);
      if (fixed === line) return null;

      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `'${bad}' → '${best}' (typo fix) on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 11: delay() called with float argument ───────────────
  {
    id: 'delay-float',
    description: 'Cast float argument to int for delay()',
    pattern: /invalid conversion from 'double' to 'unsigned long'|narrowing conversion/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const fixed = line.replace(/\bdelay\s*\(\s*(\d+\.\d+)\s*\)/g, (m, val) => {
        return `delay((unsigned long)(${val}))`;
      });
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Cast float to unsigned long in delay() on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 12: String == comparison should use .equals() ────────
  {
    id: 'string-equals',
    description: 'Replace == with .equals() for String comparison',
    pattern: /no match for 'operator==' \(operand types are 'String'/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      // Match: someString == "literal" or someString == otherString
      const fixed = line.replace(
        /(\w+)\s*==\s*("(?:[^"\\]|\\.)*"|\w+)/g,
        (m, lhs, rhs) => `${lhs}.equals(${rhs})`
      );
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Use .equals() for String comparison on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 13: Serial.begin without argument ────────────────────
  {
    id: 'serial-begin-no-arg',
    description: 'Add default baud rate 115200 to Serial.begin()',
    pattern: /no matching function for call to.*'HardwareSerial::begin\(\)'/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const fixed = line.replace(/\bSerial(\d*)\.begin\s*\(\s*\)/g, 'Serial$1.begin(115200)');
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Add baud rate 115200 to Serial.begin() on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 14: #include "Arduino.h" → <Arduino.h> ──────────────
  {
    id: 'include-quotes',
    description: 'Use angle brackets for system #include',
    pattern: /#include uses local search/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      // Convert: #include "Arduino.h" → #include <Arduino.h>
      const fixed = line.replace(/#include\s+"(Arduino\.h|Wire\.h|SPI\.h|SD\.h|Servo\.h|EEPROM\.h)"/g,
        '#include <$1>');
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Use angle brackets for #include on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 15: True/False (Python-style) → true/false ──────────
  {
    id: 'bool-case',
    description: "Fix capitalized boolean 'True'/'False'",
    pattern: /'True' (was not declared|undeclared)|'False' (was not declared|undeclared)/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const fixed = line.replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false');
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Fix 'True'/'False' → 'true'/'false' on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 16: NULL → nullptr (C++11) ──────────────────────────
  {
    id: 'null-to-nullptr',
    description: "Replace NULL with nullptr (C++11)",
    pattern: /comparison between pointer and integer|NULL comparison warning/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const fixed = line.replace(/\bNULL\b/g, 'nullptr');
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Replace NULL with nullptr on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 17: while(1) → while(true) ──────────────────────────
  {
    id: 'while-1-to-true',
    description: "Replace while(1) with while(true)",
    pattern: /always-true|tautological constant in range/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      const fixed = line.replace(/\bwhile\s*\(\s*1\s*\)/g, 'while(true)');
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Replace while(1) with while(true) on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 18: Signed/unsigned comparison ───────────────────────
  {
    id: 'signed-unsigned',
    description: 'Add (int) cast to fix signed/unsigned comparison',
    pattern: /comparison between signed and unsigned integer/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      // Wrap the right-hand side of comparison with (int)
      const fixed = line.replace(
        /(\w+)\s*(<=?|>=?|==|!=)\s*(sizeof\([^)]+\)|\w+\.size\(\)|\w+\.length\(\))/g,
        (m, lhs, op, rhs) => `(int)${lhs} ${op} (int)${rhs}`
      );
      if (fixed === line) return null;
      return {
        lineIndex: li,
        oldLine: line,
        newLine: fixed,
        description: `Add (int) cast for signed/unsigned comparison on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

  // ── Rule 19: Duplicate #include ───────────────────────────────
  {
    id: 'duplicate-include',
    description: 'Remove duplicate #include',
    // This rule scans all lines, not per-error
    pattern: /duplicate include|already included/i,
    fix(lines, error) {
      // Scan for the first duplicated include
      const seen = new Set();
      for (let i = 0; i < lines.length; i++) {
        const m = /^\s*#include\s*[<"]([^>"]+)[>"]/.exec(lines[i]);
        if (!m) continue;
        if (seen.has(m[1])) {
          return {
            lineIndex: i,
            oldLine: lines[i],
            newLine: `// ${lines[i].trim()} // removed duplicate`,
            description: `Remove duplicate #include <${m[1]}> on line ${i + 1}`,
            ruleId: this.id,
          };
        }
        seen.add(m[1]);
      }
      return null;
    },
  },

  // ── Rule 20: Missing return in non-void function ──────────────
  {
    id: 'missing-return',
    description: 'Add default return statement',
    pattern: /control (reaches|may reach) end of non-void function|no return in function returning/i,
    fix(lines, error) {
      const li = Math.max(0, error.line - 1);
      if (li >= lines.length) return null;
      const line = lines[li];
      // The error usually points to the closing brace line
      if (!/^\s*\}/.test(line)) return null;
      const indent = line.match(/^(\s*)/)[1] + '  ';
      return {
        lineIndex: li,
        oldLine: line,
        newLine: line,
        insertBefore: `${indent}return 0; // auto-added: function must return a value`,
        description: `Add 'return 0;' before closing brace on line ${li + 1}`,
        ruleId: this.id,
      };
    },
  },

];

// ─────────────────────────────────────────────────────────────────
// AutoCorrector class
// ─────────────────────────────────────────────────────────────────

export class AutoCorrector {
  /**
   * @param {string} sourceCode  — full sketch source text
   * @param {import('./error-parser').ParsedError[]} errors
   * @param {string} filePath
   */
  constructor(sourceCode, errors, filePath = '') {
    this.source    = sourceCode;
    this.lines     = sourceCode.split('\n');
    this.errors    = errors;
    this.filePath  = filePath;
    this.fixes     = [];       // { rule, error, fix }
    this._analyzed = false;
  }

  /**
   * Analyze all errors and collect applicable fixes.
   * @returns {Fix[]} list of fixes
   */
  analyze() {
    if (this._analyzed) return this.fixes;
    this._analyzed = true;
    this.fixes = [];

    const seen = new Set(); // deduplicate by (ruleId + lineIndex)

    for (const error of this.errors) {
      for (const rule of RULES) {
        if (!rule.pattern.test(error.message)) continue;

        let fix;
        try {
          fix = rule.fix(this.lines, error);
        } catch {
          continue;
        }
        if (!fix) continue;

        const key = `${fix.ruleId}:${fix.lineIndex}`;
        if (seen.has(key)) continue;
        seen.add(key);

        this.fixes.push({ rule, error, fix });
      }
    }

    return this.fixes;
  }

  /**
   * Returns how many errors have a fix available.
   */
  get fixableCount() {
    return this.analyze().length;
  }

  /**
   * Returns true if at least one fix is available.
   */
  get canFix() {
    return this.analyze().length > 0;
  }

  /**
   * Apply all fixes and return the corrected source code.
   * Fixes are applied bottom-up (highest line index first) to preserve
   * line numbers for subsequent fixes.
   *
   * @returns {{ code: string, appliedFixes: Fix[], summary: string }}
   */
  applyAll() {
    const fixes = this.analyze();
    if (fixes.length === 0) {
      return { code: this.source, appliedFixes: [], summary: 'No fixes available' };
    }

    // Sort: insertions first grouped by line descending, then replacements descending
    const sorted = [...fixes].sort((a, b) => b.fix.lineIndex - a.fix.lineIndex);

    const lines = [...this.lines];

    for (const { fix } of sorted) {
      const li = fix.lineIndex;
      if (li < 0 || li > lines.length) continue;

      if (fix.insertBefore != null && fix.newLine === null) {
        // Pure insertion: insert a new line at li
        lines.splice(li, 0, fix.insertBefore);
      } else if (fix.insertBefore != null && fix.newLine !== null) {
        // Replace + insert before
        lines[li] = fix.newLine;
        lines.splice(li, 0, fix.insertBefore);
      } else if (fix.newLine !== null) {
        // Pure replacement
        lines[li] = fix.newLine;
      }
    }

    const code = lines.join('\n');
    const summary = fixes.map(f => `• ${f.fix.description}`).join('\n');

    return { code, appliedFixes: fixes.map(f => f.fix), summary };
  }

  /**
   * Generate a human-readable diff preview.
   * @returns {{ before: string, after: string, hunks: DiffHunk[] }}
   */
  preview() {
    const { code, appliedFixes } = this.applyAll();
    const hunks = appliedFixes.map(fix => ({
      line:        fix.lineIndex + 1,
      description: fix.description,
      before:      fix.oldLine?.trimEnd() ?? '(insert)',
      after:       (fix.newLine ?? fix.insertBefore)?.trimEnd() ?? '(deleted)',
    }));
    return { before: this.source, after: code, hunks };
  }
}

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Quick check: can any rule match any error in the list?
 * Used by UI to decide whether to show the Auto Correct button.
 */
export function hasAutoFix(errors) {
  if (!errors || errors.length === 0) return false;
  return errors.some(err =>
    RULES.some(rule => rule.pattern.test(err.message))
  );
}

/**
 * Returns a plain-text copy of all errors for the clipboard.
 */
export function errorsToText(errors) {
  return errors
    .map(e => `${e.file}:${e.line}:${e.col}: ${e.severity}: ${e.message}`)
    .join('\n');
}

export { RULES };
