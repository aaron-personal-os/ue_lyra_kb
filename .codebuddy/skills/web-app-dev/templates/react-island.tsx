/**
 * {{ComponentName}} — React Island
 *
 * Purpose: {{description}}
 * Hydration: client:idle (change to client:load if immediate interaction needed)
 * State: {{localStorage key if persistent, or "component-local"}}
 *
 * Usage in Astro:
 *   <{{ComponentName}} client:idle prop={value} />
 */

import { useState, useEffect, useRef, useCallback } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
  /** Example prop — replace with actual props */
  title?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'lyra-kb-{{feature}}';

// ─── Component ────────────────────────────────────────────────────────────────

export default function ComponentName({ title }: Props) {
  // State
  const [isActive, setIsActive] = useState(false);

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);

  // ─── Effects ──────────────────────────────────────────────────────────────

  useEffect(() => {
    // Guard: only run in browser
    if (typeof window === 'undefined') return;

    // Load persisted state (if applicable)
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setIsActive(parsed.isActive ?? false);
      } catch {}
    }

    // Cleanup
    return () => {
      // Remove event listeners, observers, etc.
    };
  }, []);

  // ─── Handlers ─────────────────────────────────────────────────────────────

  const handleToggle = useCallback(() => {
    setIsActive((prev) => {
      const next = !prev;
      // Persist to localStorage
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ isActive: next }));
      return next;
    });
  }, []);

  // ─── Keyboard shortcuts (if needed) ───────────────────────────────────────

  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      // Example: Ctrl+K to toggle
      if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        handleToggle();
      }
    };
    window.addEventListener('keydown', handleKeydown);
    return () => window.removeEventListener('keydown', handleKeydown);
  }, [handleToggle]);

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      ref={containerRef}
      className="component-container"
      style={{
        // Use CSS variables for theming
        color: 'var(--text-primary)',
        background: 'var(--surface-1)',
        borderColor: 'var(--border)',
      }}
    >
      {title && <h3>{title}</h3>}
      <button onClick={handleToggle}>
        {isActive ? 'Active' : 'Inactive'}
      </button>
    </div>
  );
}
