import { useRef, useEffect, useImperativeHandle, forwardRef, useState } from 'react';
import MonacoEditor from '@monaco-editor/react';
import { loader } from '@monaco-editor/react';
import './Editor.css';

let _monacoSetupDone = false;

async function setupMonacoLanguageAndTheme() {
  if (_monacoSetupDone) return;
  _monacoSetupDone = true;

  console.log('📦 Initializing Monaco editor...');
  
  try {
    const monaco = await loader.init();
    console.log('✓ Monaco loader initialized');

    // Register Arduino language
    const langs = monaco.languages.getLanguages();
    if (!langs.find(l => l.id === 'arduino')) {
      monaco.languages.register({
        id: 'arduino',
        aliases: ['Arduino', 'ino'],
        extensions: ['.ino', '.pde']
      });
      console.log('✓ Arduino language registered');
    }

    // Define companion-dark theme
    monaco.editor.defineTheme('companion-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'keyword', foreground: '#00979D', fontStyle: 'bold' },
        { token: 'keyword.type', foreground: '#00979D', fontStyle: 'bold' },
        { token: 'keyword.control', foreground: '#C678DD', fontStyle: 'bold' },
        { token: 'preprocessor', foreground: '#C678DD' },
        { token: 'function', foreground: '#61AFEF' },
        { token: 'type.identifier', foreground: '#61AFEF' },
        { token: 'constant', foreground: '#56B6C2', fontStyle: 'bold' },
        { token: 'number', foreground: '#D19A66' },
        { token: 'number.hex', foreground: '#D19A66' },
        { token: 'string', foreground: '#98C379' },
        { token: 'comment', foreground: '#5C6370', fontStyle: 'italic' },
        { token: 'operator', foreground: '#ABB2BF' },
        { token: 'delimiter', foreground: '#ABB2BF' },
        { token: 'variable', foreground: '#E06C75' },
      ],
      colors: {
        'editor.background': '#1a1e24',
        'editor.foreground': '#ABB2BF',
        'editorLineNumber.foreground': '#495162',
        'editorLineNumber.activeForeground': '#8B949E',
        'editor.selectionBackground': '#264F78',
        'editor.lineHighlightBackground': '#21262D',
      }
    });
    console.log('✓ Theme defined');

    // Simpler, more explicit tokenizer
    const InoTokens = {
      tokenizer: {
        root: [
          // Preprocessor
          [/^[ \t]*#\s*(?:include|define|ifdef|ifndef|endif|if|else|pragma)\b/, 'preprocessor'],
          
          // Comments
          [/\/\/.*$/, 'comment'],
          [/\/\*/, { token: 'comment', next: '@comment' }],
          
          // Strings
          [/"(?:[^"\\]|\\.)*"/, 'string'],
          [/'(?:[^'\\]|\\.)*'/, 'string'],
          
          // Numbers
          [/0[xX][0-9a-fA-F]+/, 'number.hex'],
          [/0[bB][01]+/, 'number'],
          [/\d+\.\d+/, 'number'],
          [/\d+/, 'number'],
          
          // Type keywords (must come before identifier check)
          [/\b(void|int|long|unsigned|char|byte|float|double|boolean|bool|String|uint8_t|uint16_t|uint32_t|int8_t|int16_t|int32_t|size_t|word|short)\b/, 'keyword.type'],
          
          // Control keywords
          [/\b(if|else|for|while|do|switch|case|break|continue|return|goto|default)\b/, 'keyword.control'],
          
          // Other keywords
          [/\b(const|static|volatile|extern|typedef|struct|class|public|private|protected|new|delete|namespace|inline|virtual|true|false|null|NULL|nullptr)\b/, 'keyword'],
          
          // Arduino constants
          [/\b(HIGH|LOW|INPUT|OUTPUT|INPUT_PULLUP|INPUT_PULLDOWN|LED_BUILTIN|PI|TWO_PI|HALF_PI)\b/, 'constant'],
          
          // Arduino functions - must use token that theme recognizes
          [/\b(pinMode|digitalWrite|digitalRead|analogRead|analogWrite|delay|millis|micros|Serial|setup|loop|random|map|constrain|attachInterrupt|Wire|SPI)\b/, 'type.identifier'],
          
          // Identifiers and function calls
          [/[a-zA-Z_]\w*(?=\()/, 'function'],
          [/[a-zA-Z_]\w*/, 'variable'],
          
          // Operators and brackets
          [/[{}()\[\]]/, 'operator'],
          [/[<>=!&|^~?:+\-*/%]/, 'operator'],
          [/[;,.]/, 'delimiter'],
          
          // Whitespace
          [/\s+/, 'white'],
        ],
        comment: [
          [/[^/*]+/, 'comment'],
          [/\*\//, { token: 'comment', next: '@pop' }],
          [/[/*]/, 'comment'],
        ]
      }
    };

    monaco.languages.setMonarchTokensProvider('arduino', InoTokens);
    console.log('✓ Tokenizer registered');

    // Language configuration
    monaco.languages.setLanguageConfiguration('arduino', {
      comments: { lineComment: '//', blockComment: ['/*', '*/'] },
      brackets: [['{', '}'], ['[', ']'], ['(', ')']],
      autoClosingPairs: [
        { open: '{', close: '}' },
        { open: '[', close: ']' },
        { open: '(', close: ')' },
        { open: '"', close: '"', notIn: ['string', 'comment'] },
        { open: "'", close: "'", notIn: ['string', 'comment'] },
      ],
      indentationRules: {
        increaseIndentPattern: /^((?!\/\/).)*({\s*|[([]\s*)$/,
        decreaseIndentPattern: /^\s*(}|[)\]])/,
      }
    });
    console.log('✓ Language configured');
    console.log('✅ Monaco setup complete');

  } catch (error) {
    console.error('❌ Setup error:', error);
  }
}

// Start setup immediately
if (typeof window !== 'undefined') {
  setupMonacoLanguageAndTheme();
}

// ─────────────────────────────────────────────────────────────────
// Editor Component
// ─────────────────────────────────────────────────────────────────

const Editor = forwardRef(function Editor(
  { value = '', onChange, fontSize = 14, wordWrap = false, errorMarkers = [], onCursorChange },
  ref
) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const [editorReady, setEditorReady] = useState(false);
  const [useFallback, setUseFallback] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (!editorReady && !useFallback) {
        console.warn('⏱️ Monaco timeout - using fallback');
        setUseFallback(true);
      }
    }, 8000);
    return () => clearTimeout(timeout);
  }, [editorReady, useFallback]);

  useEffect(() => {
    const ed = editorRef.current;
    const monaco = monacoRef.current;
    if (!ed || !monaco) return;

    const model = ed.getModel();
    if (model) {
      monaco.editor.setModelMarkers(model, 'arduino', errorMarkers);
    }
  }, [errorMarkers]);

  const handleMount = (editor, monaco) => {
    console.log('✓ handleMount: Editor mounted');
    editorRef.current = editor;
    monacoRef.current = monaco;

    try {
      monaco.editor.setTheme('companion-dark');
      console.log('✓ Theme set');

      const model = editor.getModel();
      if (model && model.getLanguageId() !== 'arduino') {
        monaco.editor.setModelLanguage(model, 'arduino');
        console.log('✓ Language set to arduino');
      }
      
      setEditorReady(true);
    } catch (error) {
      console.error('❌ handleMount error:', error);
      setUseFallback(true);
    }
  };

  useImperativeHandle(ref, () => ({
    focus: () => editorRef.current?.focus(),
    formatDocument: () => editorRef.current?.getAction('editor.action.formatDocument')?.run(),
    goToLine: (line) => {
      const ed = editorRef.current;
      if (ed) {
        ed.revealLineInCenter(line);
        ed.setPosition({ lineNumber: line, column: 1 });
        ed.focus();
      }
    },
    findWidget: () => editorRef.current?.getAction('actions.find')?.run(),
    replaceWidget: () => editorRef.current?.getAction('editor.action.startFindReplaceAction')?.run(),
  }));

  if (useFallback) {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        style={{
          width: '100%',
          height: '100%',
          padding: '12px',
          fontSize: `${fontSize}px`,
          fontFamily: "'Fira Code', monospace",
          backgroundColor: '#1a1e24',
          color: '#abb2bf',
          border: 'none',
          outline: 'none',
          resize: 'none',
        }}
      />
    );
  }

  return (
    <MonacoEditor
      height="100%"
      defaultLanguage="arduino"
      language="arduino"
      theme="companion-dark"
      value={value}
      onChange={(v) => onChange?.(v ?? '')}
      onMount={handleMount}
      onError={(error) => {
        console.error('❌ Monaco error:', error);
        setUseFallback(true);
      }}
      options={{
        fontSize,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        fontLigatures: true,
        lineHeight: 22,
        tabSize: 2,
        insertSpaces: true,
        wordWrap: wordWrap ? 'on' : 'off',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderLineHighlight: 'gutter',
        padding: { top: 12, bottom: 12 },
      }}
    />
  );
});

Editor.displayName = 'Editor';
export default Editor;
