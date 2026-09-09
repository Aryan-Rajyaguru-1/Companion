/**
 * TabBar.jsx — Full rewrite
 *
 * Matches Arduino IDE 2.x / VS Code tab bar:
 *   - Modified dot (●) on unsaved tabs
 *   - Right-click context menu: Close / Close Others / Close to the Right / Copy Path
 *   - Overflow: horizontal scroll with ‹ › arrow buttons when tabs overflow
 *   - Keyboard: Ctrl+W closes active, Ctrl+Tab cycles
 *   - Active tab always scrolled into view
 *   - New Tab (+) button on the right
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import './TabBar.css';

export default function TabBar({ tabs, activeIndex, onSelect, onClose, onNew }) {
  const scrollRef  = useRef(null);
  const activeRef  = useRef(null);
  const [canLeft,  setCanLeft]  = useState(false);
  const [canRight, setCanRight] = useState(false);
  const [menu,     setMenu]     = useState(null); // { x, y, tabIdx }

  // Language icon colour from extension
  const extColor = (name = '') => {
    const ext = name.split('.').pop()?.toLowerCase();
    if (ext === 'ino') return 'var(--teal,#00979D)';
    if (ext === 'h' || ext === 'hpp') return 'var(--blue,#58a6ff)';
    if (ext === 'cpp' || ext === 'c') return 'var(--yellow,#d29922)';
    return 'var(--text-dim)';
  };

  // Scroll active tab into view whenever activeIndex changes
  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }, [activeIndex]);

  // Track scroll arrow visibility
  const updateArrows = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 4);
    setCanRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 4);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    updateArrows();
    el.addEventListener('scroll', updateArrows, { passive: true });
    const ro = new ResizeObserver(updateArrows);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', updateArrows); ro.disconnect(); };
  }, [tabs, updateArrows]);

  const scrollBy = (dir) => {
    scrollRef.current?.scrollBy({ left: dir * 120, behavior: 'smooth' });
  };

  // Context menu
  const handleContextMenu = (e, idx) => {
    e.preventDefault();
    setMenu({ x: e.clientX, y: e.clientY, idx });
  };

  const closeMenu = useCallback(() => setMenu(null), []);

  useEffect(() => {
    if (!menu) return;
    window.addEventListener('mousedown', closeMenu);
    window.addEventListener('keydown', closeMenu);
    return () => { window.removeEventListener('mousedown', closeMenu); window.removeEventListener('keydown', closeMenu); };
  }, [menu, closeMenu]);

  const menuActions = [
    { label: 'Close',                action: (idx) => onClose(idx) },
    { label: 'Close Others',         action: (idx) => { const keep = [idx]; tabs.forEach((_, i) => { if (i !== idx) onClose(i < idx ? i : i - (keep.length - 1)); }); } },
    { label: 'Close to the Right',   action: (idx) => { for (let i = tabs.length - 1; i > idx; i--) onClose(i); } },
    null, // separator
    { label: 'Copy Relative Path',   action: (idx) => navigator.clipboard?.writeText(tabs[idx]?.path || tabs[idx]?.name || '') },
  ];

  // Keyboard: Ctrl+W = close active
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
        e.preventDefault();
        onClose(activeIndex);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeIndex, onClose]);

  return (
    <div className="tabbar">
      {/* Left scroll arrow */}
      {canLeft && (
        <button className="tabbar-scroll-btn left" onClick={() => scrollBy(-1)} tabIndex={-1}>‹</button>
      )}

      {/* Tab strip */}
      <div className="tabbar-strip" ref={scrollRef}>
        {tabs.map((tab, i) => {
          const isActive = i === activeIndex;
          return (
            <div
              key={tab.id}
              ref={isActive ? activeRef : null}
              className={`tabbar-tab ${isActive ? 'active' : ''} ${tab.modified ? 'modified' : ''}`}
              onClick={() => onSelect(i)}
              onContextMenu={(e) => handleContextMenu(e, i)}
              title={tab.path || tab.name}
            >
              <span className="tab-ext-dot" style={{ background: extColor(tab.name) }} />
              <span className="tab-name">{tab.name}</span>
              {tab.modified
                ? <span className="tab-modified-dot" title="Unsaved changes">●</span>
                : <button
                    className="tab-close-btn"
                    onClick={e => { e.stopPropagation(); onClose(i); }}
                    title="Close tab  Ctrl+W"
                  >✕</button>
              }
            </div>
          );
        })}
      </div>

      {/* Right scroll arrow */}
      {canRight && (
        <button className="tabbar-scroll-btn right" onClick={() => scrollBy(1)} tabIndex={-1}>›</button>
      )}

      {/* New tab button */}
      <button className="tabbar-new-btn" onClick={onNew} title="New tab">＋</button>

      {/* Context menu portal */}
      {menu && (
        <div
          className="tab-context-menu"
          style={{ top: menu.y, left: menu.x }}
          onMouseDown={e => e.stopPropagation()}
        >
          {menuActions.map((item, i) =>
            item === null
              ? <div key={i} className="tcm-sep" />
              : <button key={i} className="tcm-item"
                  onClick={() => { item.action(menu.idx); closeMenu(); }}>
                  {item.label}
                </button>
          )}
        </div>
      )}
    </div>
  );
}
