/**
 * TerminalPanel — VSCode-style embedded terminal Island (dev-only).
 *
 * Mounted by TutorialLayout.astro behind an `import.meta.env.DEV` guard so
 * the entire bundle (this file + xterm dependencies) is tree-shaken out of
 * `astro build` artifacts.
 *
 * Responsibilities:
 *  - Open one WebSocket per tab to terminal-server (ws://127.0.0.1:4322).
 *  - Persist visibility / height / tab list in localStorage.
 *  - Keyboard shortcut: Ctrl+J toggles panel; Ctrl+Shift+J adds a new tab.
 *  - Inject current tutorial path into the header for context-aware prompts.
 *
 * Connection model (ADR-0003 v0.2):
 *  - No token. terminal-server only listens on 127.0.0.1 and validates Origin,
 *    which is sufficient for single-user local development.
 *  - xterm is imported dynamically so the module is only fetched after the
 *    user actually opens the panel.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import '@/styles/terminal.css';

// ----- Types -----

interface TabState {
  id: string;
  title: string;
}

interface SerializedState {
  visible: boolean;
  heightPx: number;
  tabs: TabState[];
  activeId: string | null;
}

// ----- Constants -----

const STORAGE_KEY = 'lyra:terminal:v1';
const DEFAULT_HEIGHT_VH = 30;
const MIN_HEIGHT_PX = 120;
const WS_PROTOCOL = 'lyra-terminal-v1';
// Hard-coded local endpoint. Override via window.__LYRA_TERMINAL_WS if needed.
const DEFAULT_WS_URL = 'ws://127.0.0.1:4322';
const SHORTCUT_LABEL = 'Ctrl+J';

// ----- Helpers -----

function loadState(): SerializedState {
  if (typeof window === 'undefined') {
    return { visible: false, heightPx: 0, tabs: [], activeId: null };
  }
  const defaultHeight = Math.round((window.innerHeight * DEFAULT_HEIGHT_VH) / 100);
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { visible: false, heightPx: defaultHeight, tabs: [], activeId: null };
    }
    const parsed = JSON.parse(raw) as Partial<SerializedState>;
    return {
      visible: Boolean(parsed.visible),
      heightPx: Math.max(MIN_HEIGHT_PX, Number(parsed.heightPx) || defaultHeight),
      tabs: Array.isArray(parsed.tabs) ? parsed.tabs : [],
      activeId: typeof parsed.activeId === 'string' ? parsed.activeId : null,
    };
  } catch {
    return { visible: false, heightPx: defaultHeight, tabs: [], activeId: null };
  }
}

function saveState(state: SerializedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {}
}

function readLessonPath(): string | null {
  if (typeof document === 'undefined') return null;
  const article = document.querySelector('article[data-lesson-path]') as HTMLElement | null;
  if (article?.dataset?.lessonPath) return article.dataset.lessonPath;
  const m = location.pathname.match(/^\/series\/([^/]+)\/([^/?#]+)/);
  if (m) return `30-tutorials/${m[1]}/${m[2]}`;
  return null;
}

function getWsUrl(): string {
  if (typeof window !== 'undefined' && (window as any).__LYRA_TERMINAL_WS) {
    return String((window as any).__LYRA_TERMINAL_WS);
  }
  return DEFAULT_WS_URL;
}

function genTabId() {
  return 't_' + Math.random().toString(36).slice(2, 9);
}

// ----- Per-tab session controller -----

interface TabHandle {
  id: string;
  setHostElement: (el: HTMLDivElement | null) => void;
  fit: () => void;
  dispose: () => void;
  readonly status: 'connecting' | 'open' | 'error' | 'closed';
  readonly errorMessage?: string;
  /** Subscribe BEFORE calling start() so no early state change is missed. */
  onStatusChange: (cb: (s: TabHandle['status'], err?: string) => void) => void;
  /** Open the WebSocket. Must be called after onStatusChange is registered. */
  start: () => void;
  sendInput: (text: string) => void;
}

async function createTabHandle(id: string): Promise<TabHandle> {
  const [{ Terminal }, { FitAddon }, { WebLinksAddon }] = await Promise.all([
    import('@xterm/xterm'),
    import('@xterm/addon-fit'),
    import('@xterm/addon-web-links'),
    // Static side-effect import via Vite — guarantees the stylesheet is in
    // the document BEFORE Terminal.open() runs, avoiding an off-by-one row
    // where xterm's first measure uses a fallback font size.
    import('@xterm/xterm/css/xterm.css'),
  ]);

  const term = new Terminal({
    fontSize: 14,
    // Default 1.0 clips descenders/ascenders for CJK glyphs (中文 / 日本語),
    // making each row look "cut off at the bottom". 1.2 gives enough room
    // without making the terminal feel sparse.
    lineHeight: 1.2,
    fontFamily:
      "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    cursorBlink: true,
    cursorStyle: 'bar',
    allowProposedApi: true,
    convertEol: false,
    theme: {
      background: '#0d1117',
      foreground: '#d1d5db',
      cursor: '#38bdf8',
      cursorAccent: '#0d1117',
      selectionBackground: 'rgba(56,189,248,0.35)',
      black: '#1e293b',
      red: '#f87171',
      green: '#4ade80',
      yellow: '#facc15',
      blue: '#60a5fa',
      magenta: '#c084fc',
      cyan: '#22d3ee',
      white: '#e2e8f0',
      brightBlack: '#475569',
      brightRed: '#fca5a5',
      brightGreen: '#86efac',
      brightYellow: '#fde68a',
      brightBlue: '#93c5fd',
      brightMagenta: '#d8b4fe',
      brightCyan: '#67e8f9',
      brightWhite: '#f8fafc',
    },
  });
  const fitAddon = new FitAddon();
  term.loadAddon(fitAddon);
  term.loadAddon(new WebLinksAddon());

  let host: HTMLDivElement | null = null;
  let attached = false;
  let status: TabHandle['status'] = 'connecting';
  let errorMessage: string | undefined;
  let statusCb: ((s: TabHandle['status'], err?: string) => void) | null = null;
  let ws: WebSocket | null = null;
  let connectTimeoutId: number | null = null;

  const setStatus = (s: TabHandle['status'], err?: string) => {
    status = s;
    errorMessage = err;
    statusCb?.(s, err);
  };

  const sendResize = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
  };

  let bootHintTimer: number | null = null;
  let bootHintShown = false;

  const cancelBootHint = () => {
    if (bootHintTimer != null) {
      window.clearTimeout(bootHintTimer);
      bootHintTimer = null;
    }
    // If the hint was already written to xterm, clear the line so it doesn't
    // linger above the prompt. Use ANSI: move up 1, erase line, move col 0.
    if (bootHintShown) {
      term.write('\x1b[1A\x1b[2K\r');
      bootHintShown = false;
    }
  };

  const showBootHint = () => {
    if (bootHintShown) return;
    bootHintShown = true;
    // Soft hint so the user knows we're alive while shell rc files run
    // (pyenv/nvm/conda init can take several seconds).
    term.writeln(
      '\x1b[90m启动 shell 中…（如果较慢，通常是 .zshrc 中的 pyenv/nvm 初始化）\x1b[0m'
    );
  };

  const start = () => {
    if (ws) return; // already started
    // eslint-disable-next-line no-console
    console.log('[TerminalPanel] connecting to', getWsUrl());
    ws = new WebSocket(getWsUrl(), [WS_PROTOCOL]);
    ws.binaryType = 'arraybuffer';

    ws.addEventListener('open', () => {
      // eslint-disable-next-line no-console
      console.log('[TerminalPanel] WebSocket OPEN');
      setStatus('open');
      // Show a "booting" hint only if shell still hasn't echoed after 1.5s.
      // Most launches are faster than this, so the hint stays invisible in
      // the common case.
      bootHintTimer = window.setTimeout(showBootHint, 1500);
      queueMicrotask(() => {
        if (host && attached) {
          try { fitAddon.fit(); } catch {}
          sendResize();
        }
      });
    });

    ws.addEventListener('message', (ev) => {
      // Any non-control message means the shell is alive — cancel boot hint.
      // We do this BEFORE branching so JSON control frames, plain-text
      // payloads and binary streams all clear the hint uniformly.
      const isJsonControl =
        typeof ev.data === 'string' && ev.data.startsWith('{');
      if (!isJsonControl) {
        cancelBootHint();
      }

      if (typeof ev.data === 'string') {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'exit') {
            term.writeln(
              `\r\n\x1b[90m[process exited${
                msg.exitCode != null ? ` code=${msg.exitCode}` : ''
              }]\x1b[0m`
            );
            setStatus('closed');
            return;
          }
          if (msg.type === 'error' && typeof msg.message === 'string') {
            term.writeln(`\r\n\x1b[31m[server error] ${msg.message}\x1b[0m`);
            setStatus('error', msg.message);
            return;
          }
          // 'ready' or unknown control — ignore
          return;
        } catch {
          term.write(ev.data);
        }
        return;
      }
      term.write(new Uint8Array(ev.data as ArrayBuffer));
    });

    ws.addEventListener('error', (ev) => {
      // eslint-disable-next-line no-console
      console.error('[TerminalPanel] WebSocket error', ev);
      if (status === 'connecting') {
        setStatus(
          'error',
          '无法连接 terminal-server（' + getWsUrl() + '）。请确认 ./start.sh / start.bat 已成功启动。'
        );
      }
    });
    ws.addEventListener('close', (ev) => {
      // eslint-disable-next-line no-console
      console.warn('[TerminalPanel] WebSocket closed', { code: ev.code, reason: ev.reason });
      if (connectTimeoutId != null) { window.clearTimeout(connectTimeoutId); connectTimeoutId = null; }
      if (status === 'connecting') {
        const hint =
          ev.code === 1006
            ? '握手失败（可能：terminal-server 未启动、端口冲突、或 Origin 校验拒绝）'
            : `连接关闭 (code=${ev.code}${ev.reason ? `, reason=${ev.reason}` : ''})`;
        setStatus('error', hint);
      } else if (status !== 'error') {
        setStatus('closed');
      }
    });

    // Safety net: if neither open nor error fires within 5s, declare timeout.
    connectTimeoutId = window.setTimeout(() => {
      if (status === 'connecting') {
        try { ws?.close(); } catch {}
        setStatus(
          'error',
          '连接超时（>5s）。terminal-server 可能未启动，或 Node 进程被卡住。'
        );
      }
    }, 5000);
    ws.addEventListener('open', () => {
      if (connectTimeoutId != null) { window.clearTimeout(connectTimeoutId); connectTimeoutId = null; }
    });
  };

  term.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(data);
  });

  // Some keys (notably Esc on Chrome/macOS in certain focus states) never
  // reach xterm's textarea. attachCustomKeyEventHandler runs for every
  // keydown the textarea sees, giving us a chance to forward Esc directly
  // before xterm's own logic might drop or buffer it.
  term.attachCustomKeyEventHandler((e) => {
    if (e.type !== 'keydown') return true;
    if (e.key === 'Escape' && !e.metaKey && !e.ctrlKey && !e.altKey) {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('\x1b');
      return false;
    }
    return true;
  });

  term.onResize(() => sendResize());

  return {
    id,
    get status() { return status; },
    get errorMessage() { return errorMessage; },
    setHostElement(el) {
      if (!el) {
        host = null;
        return;
      }
      host = el;
      if (!attached) {
        term.open(el);
        attached = true;
      }
      try { fitAddon.fit(); } catch {}
      sendResize();
      term.focus();
    },
    fit() {
      if (!host) return;
      try { fitAddon.fit(); } catch {}
      sendResize();
    },
    dispose() {
      if (connectTimeoutId != null) { window.clearTimeout(connectTimeoutId); connectTimeoutId = null; }
      try { ws?.close(); } catch {}
      try { term.dispose(); } catch {}
    },
    onStatusChange(cb) {
      statusCb = cb;
    },
    start,
    sendInput(text) {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(text);
    },
  };
}

// ----- Component -----

export default function TerminalPanel() {
  const [visible, setVisible] = useState(false);
  const [heightPx, setHeightPx] = useState(0);
  const [tabs, setTabs] = useState<TabState[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const handlesRef = useRef<Map<string, TabHandle>>(new Map());
  const hostRefs = useRef<Map<string, HTMLDivElement | null>>(new Map());
  const [, forceUpdate] = useState(0);
  const rerender = useCallback(() => forceUpdate((n) => n + 1), []);

  const [lessonPath, setLessonPath] = useState<string | null>(null);

  // -------- Mount: load persisted state --------
  useEffect(() => {
    const initial = loadState();
    setVisible(initial.visible);
    setHeightPx(initial.heightPx);
    setTabs(initial.tabs);
    setActiveId(initial.activeId);
    setLessonPath(readLessonPath());
    setHydrated(true);
  }, []);

  // -------- Persist state --------
  useEffect(() => {
    if (!hydrated) return;
    saveState({ visible, heightPx, tabs, activeId });
  }, [visible, heightPx, tabs, activeId, hydrated]);

  // -------- Tab management --------
  const addTab = useCallback(() => {
    const id = genTabId();
    setTabs((prev) => [...prev, { id, title: `Terminal ${prev.length + 1}` }]);
    setActiveId(id);
    setVisible(true);
  }, []);

  const closeTab = useCallback(
    (id: string) => {
      const handle = handlesRef.current.get(id);
      handle?.dispose();
      handlesRef.current.delete(id);
      hostRefs.current.delete(id);
      setTabs((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (activeId === id) {
          setActiveId(next.length ? next[next.length - 1].id : null);
        }
        return next;
      });
    },
    [activeId]
  );

  // -------- Keyboard shortcut: Ctrl+J / Ctrl+Shift+J --------
  // Notes:
  //  - When focus is INSIDE the terminal panel, Ctrl+J means "newline" to
  //    the shell (equivalent of \n). We must NOT swallow it there, otherwise
  //    pressing Enter-equivalent would close the panel.
  //  - Ctrl+Shift+J is fine to intercept everywhere — shells don't bind it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey && !e.metaKey && !e.altKey && e.code === 'KeyJ')) return;
      const inPanel = (e.target as HTMLElement | null)?.closest?.(
        '.lyra-terminal-root'
      );
      if (e.shiftKey) {
        e.preventDefault();
        addTab();
        return;
      }
      // Ctrl+J without shift: only toggle when focus is OUTSIDE the panel,
      // so the shell still receives Ctrl+J as newline when typing.
      if (!inPanel) {
        e.preventDefault();
        setVisible((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [addTab]);

  // Auto-create a first tab when panel becomes visible and is empty
  useEffect(() => {
    if (visible && hydrated && tabs.length === 0) {
      addTab();
    }
  }, [visible, hydrated, tabs.length, addTab]);

  // Ensure activeId points at an existing tab
  useEffect(() => {
    if (tabs.length === 0) {
      if (activeId !== null) setActiveId(null);
      return;
    }
    if (!activeId || !tabs.find((t) => t.id === activeId)) {
      setActiveId(tabs[tabs.length - 1].id);
    }
  }, [tabs, activeId]);

  // -------- Lazy create handles for active tab --------
  useEffect(() => {
    if (!visible || !activeId) return;
    if (handlesRef.current.has(activeId)) {
      const host = hostRefs.current.get(activeId) || null;
      handlesRef.current.get(activeId)!.setHostElement(host);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const handle = await createTabHandle(activeId);
        if (cancelled) {
          handle.dispose();
          return;
        }
        // Subscribe FIRST so no early ws state change is missed.
        handle.onStatusChange(() => rerender());
        handlesRef.current.set(activeId, handle);
        const host = hostRefs.current.get(activeId) || null;
        handle.setHostElement(host);
        // Now actually open the WebSocket.
        handle.start();
        rerender();
      } catch (err: any) {
        // Surface the failure on the active tab via overlay.
        rerender();
        // eslint-disable-next-line no-console
        console.error('[TerminalPanel] failed to start tab:', err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [visible, activeId, rerender]);

  // -------- Auto-focus xterm textarea --------
  // xterm's hidden textarea must have focus or it can't receive keys —
  // and on Chrome/macOS, the bare Escape key is sometimes consumed by the
  // browser before it reaches an unfocused textarea, which is exactly the
  // bug that breaks vim's "exit INSERT mode".
  // Strategy: when the panel becomes visible / a tab becomes active,
  // schedule a focus(). Also re-focus whenever the panel area is clicked.
  useEffect(() => {
    if (!visible || !activeId) return;
    const tryFocus = () => {
      const hostEl = hostRefs.current.get(activeId);
      const ta = hostEl?.querySelector(
        'textarea.xterm-helper-textarea'
      ) as HTMLTextAreaElement | null;
      ta?.focus({ preventScroll: true });
    };
    // First attempt on next frame (xterm may not have rendered yet).
    const r1 = requestAnimationFrame(tryFocus);
    // Second attempt after a short delay (covers slow first paint).
    const r2 = window.setTimeout(tryFocus, 100);
    return () => {
      cancelAnimationFrame(r1);
      window.clearTimeout(r2);
    };
  }, [visible, activeId]);

  // -------- Resize observer for fit --------
  useEffect(() => {
    if (!activeId) return;
    const handle = handlesRef.current.get(activeId);
    if (!handle) return;
    // Re-fit on multiple frames so we catch the layout AFTER the slide-in
    // transition completes (translateY 0 → 0%, takes ~180ms via CSS).
    const r1 = requestAnimationFrame(() => handle.fit());
    const t1 = window.setTimeout(() => handle.fit(), 200);
    const t2 = window.setTimeout(() => handle.fit(), 350);
    const onResize = () => handle.fit();
    window.addEventListener('resize', onResize);
    return () => {
      cancelAnimationFrame(r1);
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      window.removeEventListener('resize', onResize);
    };
  }, [activeId, heightPx, visible]);

  // -------- Trap wheel events inside the panel --------
  // overscroll-behavior alone is not enough: when xterm has nothing to
  // scroll (no scrollback content yet), wheel events bubble straight to
  // window and scroll the article. We catch wheel events whose target is
  // inside the panel and preventDefault them. xterm registers its own
  // wheel handler with passive=false on .xterm-viewport BEFORE this
  // capture-phase listener runs (it uses addEventListener directly), so it
  // still gets to consume the scroll for its scrollback buffer; we only
  // block what would otherwise leak out.
  useEffect(() => {
    if (!visible) return;
    const onWheel = (e: WheelEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.closest('.lyra-terminal-root')) {
        e.preventDefault();
      }
    };
    // passive: false so preventDefault works.
    window.addEventListener('wheel', onWheel, { passive: false });
    return () => window.removeEventListener('wheel', onWheel);
  }, [visible]);

  // -------- Force-route Esc / arrow / fn keys to the PTY --------
  // Why this exists:
  //  - xterm relies on its hidden helper-textarea having focus.
  //  - On macOS browsers, the bare Escape key is treated as "cancel" and
  //    can blur the active textarea BEFORE xterm's own keydown handler
  //    runs. The result: Esc never reaches the PTY, vim stays in INSERT,
  //    and the next keypress goes to the page (article scroll, etc.).
  //  - Arrow / Home / End / PageUp / PageDown sometimes scroll the page
  //    even with overscroll-behavior, because the focus has fallen back
  //    to <body>.
  //
  // Fix: window-level capture-phase listener (runs BEFORE any element
  // handler, including xterm's), filters by "is the target inside the
  // terminal panel?", and writes the ANSI escape sequence directly to the
  // PTY via WebSocket. preventDefault stops the default browser action.
  useEffect(() => {
    if (!visible) return;
    const onKeyDown = (e: KeyboardEvent) => {
      // Skip if focus is outside the panel — let the page handle Esc etc.
      const target = e.target as HTMLElement | null;
      const inPanel =
        !!target?.closest?.('.lyra-terminal-root') ||
        // Focus may also be on <body> right after Esc fired its first time;
        // in that case treat as "inside" only if the panel is the active
        // panel and was the most recent click target. Cheap heuristic:
        // we always handle Esc when panel is visible — vim-style usability
        // outweighs the rare case of the user wanting Esc on the page.
        e.key === 'Escape';
      if (!inPanel) return;

      const handle = activeId ? handlesRef.current.get(activeId) : null;
      if (!handle) return;

      let seq: string | null = null;
      switch (e.key) {
        case 'Escape':       seq = '\x1b'; break;
        case 'ArrowUp':      seq = '\x1b[A'; break;
        case 'ArrowDown':    seq = '\x1b[B'; break;
        case 'ArrowRight':   seq = '\x1b[C'; break;
        case 'ArrowLeft':    seq = '\x1b[D'; break;
        case 'Home':         seq = '\x1b[H'; break;
        case 'End':          seq = '\x1b[F'; break;
        case 'PageUp':       seq = '\x1b[5~'; break;
        case 'PageDown':     seq = '\x1b[6~'; break;
        case 'Delete':       seq = '\x1b[3~'; break;
        default: return;
      }
      // Heavy modifiers belong to the browser/OS (e.g. Cmd+←).
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      e.preventDefault();
      e.stopPropagation();
      // Stop xterm's own keydown handler from also reacting to this same
      // event (otherwise vim could see two Esc presses, harmless but odd).
      (e as any).stopImmediatePropagation?.();
      handle.sendInput(seq);

      // After Esc, xterm's textarea may have been blurred by the browser.
      // Refocus it so subsequent keystrokes (e.g. `:` after Esc) still go
      // through xterm's own input pipeline (which handles Unicode, IME...).
      const hostEl = activeId ? hostRefs.current.get(activeId) : null;
      const xtermTextarea = hostEl?.querySelector(
        'textarea.xterm-helper-textarea'
      ) as HTMLTextAreaElement | null;
      xtermTextarea?.focus();
    };

    // capture: true → runs before xterm's own listener and before any
    // element-level handler in the panel.
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [visible, activeId]);

  // -------- Drag-resize handle --------
  const draggingRef = useRef(false);
  const dragStartRef = useRef<{ y: number; h: number } | null>(null);
  const onDragStart = (e: React.MouseEvent) => {
    draggingRef.current = true;
    dragStartRef.current = { y: e.clientY, h: heightPx };
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  };
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current || !dragStartRef.current) return;
      const dy = dragStartRef.current.y - e.clientY;
      const next = Math.max(
        MIN_HEIGHT_PX,
        Math.min(window.innerHeight * 0.8, dragStartRef.current.h + dy)
      );
      setHeightPx(next);
    };
    const onUp = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      dragStartRef.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  const askClaudeAboutPage = useCallback(() => {
    const handle = activeId ? handlesRef.current.get(activeId) : null;
    if (!handle || !lessonPath) return;
    handle.sendInput(`请基于 Docs/${lessonPath} 回答：`);
  }, [activeId, lessonPath]);

  useEffect(() => {
    return () => {
      handlesRef.current.forEach((h) => h.dispose());
      handlesRef.current.clear();
    };
  }, []);

  const launcherHidden = visible;
  const activeHandle = activeId ? handlesRef.current.get(activeId) : null;
  // Read status directly on each render — TabHandle exposes it as a getter,
  // and onStatusChange triggers rerender(), so the overlay stays in sync.
  // Memoising on `activeHandle` (stable object ref) would freeze it at
  // "正在连接终端..." forever.
  let overlayMessage: string | null = null;
  if (!activeHandle) {
    overlayMessage = '正在启动会话...';
  } else if (activeHandle.status === 'connecting') {
    overlayMessage = '正在连接终端...';
  } else if (activeHandle.status === 'error') {
    overlayMessage = activeHandle.errorMessage || '连接错误';
  } else if (activeHandle.status === 'closed') {
    overlayMessage = '会话已结束（按下方"+"按钮新建）';
  }
  // status === 'open' → overlayMessage stays null and overlay is not rendered.

  return (
    <>
      <button
        type="button"
        className="lyra-terminal-launcher"
        data-hidden={launcherHidden ? 'true' : 'false'}
        onClick={() => setVisible(true)}
        title={`打开终端 (${SHORTCUT_LABEL})`}
      >
        <span aria-hidden>{'>_'}</span>
        <span>终端</span>
        <kbd>{SHORTCUT_LABEL}</kbd>
      </button>

      {/* The root stays mounted whenever there are tabs, so xterm DOM
          (and its internal viewport sizing) survives a "minimize". CSS
          translateY(100%) slides it off-screen when data-visible=false. */}
      {tabs.length > 0 && (
        <div
          className="lyra-terminal-root"
          data-visible={visible ? 'true' : 'false'}
          style={{ height: heightPx ? `${heightPx}px` : undefined }}
        >
          <div
            className="lyra-terminal-resize-handle"
            onMouseDown={onDragStart}
            title="拖拽调整高度"
          />

          <div className="lyra-terminal-header">
            <div className="lyra-terminal-tabs">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="lyra-terminal-tab"
                  data-active={t.id === activeId ? 'true' : 'false'}
                  onClick={() => setActiveId(t.id)}
                  title={t.title}
                >
                  <span>{t.title}</span>
                  <span
                    role="button"
                    tabIndex={-1}
                    className="tab-close"
                    onClick={(e) => {
                      e.stopPropagation();
                      closeTab(t.id);
                    }}
                    aria-label={`关闭 ${t.title}`}
                  >
                    ×
                  </span>
                </button>
              ))}
            </div>
            <div className="lyra-terminal-actions">
              <button
                type="button"
                onClick={addTab}
                title={`新建终端 (Ctrl+Shift+J)`}
                aria-label="新建终端"
              >
                +
              </button>
              <button
                type="button"
                onClick={() => setVisible(false)}
                title={`隐藏终端 (${SHORTCUT_LABEL})`}
                aria-label="隐藏终端"
              >
                –
              </button>
              <button
                type="button"
                data-variant="close"
                onClick={() => {
                  tabs.forEach((t) => {
                    const h = handlesRef.current.get(t.id);
                    h?.dispose();
                    handlesRef.current.delete(t.id);
                    hostRefs.current.delete(t.id);
                  });
                  setTabs([]);
                  setActiveId(null);
                  setVisible(false);
                }}
                title="关闭所有终端"
                aria-label="关闭所有终端"
              >
                ×
              </button>
            </div>
          </div>

          {lessonPath && (
            <div className="lyra-terminal-context">
              <strong>Reading:</strong>
              <span>Docs/{lessonPath}</span>
              <button
                type="button"
                className="ctx-action"
                onClick={askClaudeAboutPage}
                title="在终端预填一条针对本教程的 Claude 提问命令"
              >
                基于本页提问
              </button>
            </div>
          )}

          <div
            className="lyra-terminal-body"
            // Click anywhere in the body re-focuses the active xterm so keys
            // (including Esc) reach the PTY. Without this, clicking the
            // header / context strip / launcher button steals focus and
            // subsequent keypresses go nowhere.
            onMouseDown={() => {
              const h = activeId ? handlesRef.current.get(activeId) : null;
              h?.fit();
              const hostEl = activeId ? hostRefs.current.get(activeId) : null;
              const xtermTextarea = hostEl?.querySelector(
                'textarea.xterm-helper-textarea'
              ) as HTMLTextAreaElement | null;
              xtermTextarea?.focus();
            }}
          >
            {tabs.map((t) => (
              <div
                key={t.id}
                className="xterm-host"
                ref={(el) => {
                  hostRefs.current.set(t.id, el);
                  const h = handlesRef.current.get(t.id);
                  if (h) h.setHostElement(t.id === activeId ? el : null);
                }}
                style={{ display: t.id === activeId ? 'block' : 'none' }}
              />
            ))}
            {overlayMessage && (
              <div className="lyra-terminal-overlay">
                <div>
                  {overlayMessage}
                  <div style={{ marginTop: 8 }}>
                    <code>{SHORTCUT_LABEL}</code> 关闭面板
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
