import { useState } from 'react';
import './App.css';

export default function App() {
  const [count, setCount] = useState(0);

  console.log('App component rendered');

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#1a1e24',
      color: '#abb2bf',
      fontFamily: 'monospace',
    }}>
      <h1>Companion IDE</h1>
      <p>React is working! ✓</p>
      <p>Click count: {count}</p>
      <button
        onClick={() => setCount(count + 1)}
        style={{
          padding: '10px 20px',
          backgroundColor: '#0369a1',
          color: '#fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          marginTop: '20px',
        }}
      >
        Click Me
      </button>
    </div>
  );
}
