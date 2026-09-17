// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const require = createRequire(import.meta.url);
const CompanionCLI = require('../../../electron/companion-cli.js');

describe('exported upload artifact selection', () => {
  it('never selects a merged image, even when newer or the only image', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'companion-artifacts-'));
    try {
      const sketch = path.join(root, 'Blink');
      const dir = path.join(sketch, 'build', 'esp32.esp32.esp32s3');
      fs.mkdirSync(dir, { recursive: true });
      const app = path.join(dir, 'Blink.bin');
      const merged = path.join(dir, 'Blink.ino.merged.bin');
      fs.writeFileSync(app, 'app');
      fs.utimesSync(app, new Date(1000), new Date(1000));
      fs.writeFileSync(merged, 'merged');
      // Avoid constructor side effects (config files and daemon setup).
      const cli = Object.create(CompanionCLI.prototype);
      expect(cli._findExportedBinary(sketch, 'esp32:esp32:esp32s3')).toBe(app);
      fs.unlinkSync(app);
      expect(cli._findExportedBinary(sketch, 'esp32:esp32:esp32s3')).toBeNull();
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
