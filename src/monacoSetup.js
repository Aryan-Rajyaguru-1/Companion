// monacoSetup.js — wires Monaco to the LOCAL bundle. Imported FIRST by
// main.jsx, before App, because Editor.jsx calls loader.init() at module
// scope: ES module bodies evaluate in import order, so this must run before
// the editor module is evaluated or the loader would inject its CDN script
// (which the strict CSP blocks, leaving a dead editor).
//
// Monaco used to be pointed at cdn.jsdelivr.net, which meant the editor's
// JavaScript arrived at runtime from a third-party CDN — so the CSP had to
// allow that origin and 'unsafe-eval', and the "100% local" claim was false:
// whoever served that file owned the editor inside the app.
import { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';

// The worker is bundled too, so the editor's language service runs in a local
// worker instead of reaching out for one.
self.MonacoEnvironment = {
  getWorker: () => new editorWorker(),
};

// window.monaco is the loader's FIRST check: it only injects the CDN script
// when neither the global nor loader.config({monaco}) is present. Setting the
// global is instance-proof — loader.config alone was not enough, because the
// component and the config call ended up holding different loader instances
// and the CDN branch fired anyway.
window.monaco = monaco;
loader.config({ monaco });

export { monaco };
