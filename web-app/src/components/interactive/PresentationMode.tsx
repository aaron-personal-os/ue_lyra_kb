import { useEffect, useRef, useState, useCallback } from 'react';

interface Slide {
  html: string;
  notes?: string;
  fragments?: string[];
}

interface Props {
  /** The full rendered HTML of the tutorial article */
  contentHtml: string;
  /** Series accent color for theming */
  accentColor?: string;
  /** Title shown on the first slide */
  title: string;
  /** Series name badge */
  seriesName?: string;
  /** Lesson index for display */
  lessonMeta?: string;
}

/**
 * PresentationMode - Converts tutorial content into a full-screen
 * reveal.js slide presentation.
 *
 * Splitting strategy:
 *   - Each <h2> starts a new horizontal slide
 *   - Each <h3> inside a section creates a vertical (nested) slide
 *   - Code blocks get fragment highlight (appear on next click)
 *   - Blockquotes become speaker notes
 *   - The first slide is an auto-generated title slide
 */
export default function PresentationMode({
  contentHtml,
  accentColor = '#60a5fa',
  title,
  seriesName,
  lessonMeta,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const deckRef = useRef<HTMLDivElement>(null);
  const revealInstanceRef = useRef<any>(null);

  const open = useCallback(() => {
    setIsOpen(true);
    document.body.style.overflow = 'hidden';
  }, []);

  const close = useCallback(() => {
    if (revealInstanceRef.current) {
      try { revealInstanceRef.current.destroy(); } catch { /* noop */ }
      revealInstanceRef.current = null;
    }
    // Remove injected reveal.js CSS to prevent global style pollution
    document.querySelectorAll('link[data-reveal-css]').forEach((el) => el.remove());
    setIsOpen(false);
    document.body.style.overflow = '';
  }, []);

  // Initialize reveal.js when overlay opens
  useEffect(() => {
    if (!isOpen || !deckRef.current) return;

    let cancelled = false;

    (async () => {
      // Inject reveal.js CSS (will be removed on close to avoid global pollution)
      const reset = document.createElement('link');
      reset.rel = 'stylesheet';
      reset.href = '/vendor/reveal/reset.css';
      reset.dataset.revealCss = 'true';
      document.head.appendChild(reset);

      const revealCss = document.createElement('link');
      revealCss.rel = 'stylesheet';
      revealCss.href = '/vendor/reveal/reveal.css';
      revealCss.dataset.revealCss = 'true';
      document.head.appendChild(revealCss);

      // Allow CSS to load
      await new Promise((r) => setTimeout(r, 80));
      // Dynamic import to keep initial bundle small
      const Reveal = (await import('reveal.js')).default;

      if (cancelled || !deckRef.current) return;

      // Grab article HTML from the DOM (more reliable than passing from server)
      const articleEl = document.querySelector('.prose-tutorial');
      const html = articleEl?.innerHTML || contentHtml || '';

      const slides = buildSlides(html, title, seriesName, lessonMeta, accentColor);
      const slidesContainer = deckRef.current.querySelector('.slides');
      if (slidesContainer) {
        slidesContainer.innerHTML = slides;
      }

      const deck = new Reveal(deckRef.current, {
        hash: false,
        history: false,
        controls: true,
        controlsTutorial: false,
        progress: true,
        center: true,
        disableLayout: false,
        transition: 'slide',
        transitionSpeed: 'default',
        backgroundTransition: 'fade',
        width: 1280,
        height: 720,
        margin: 0.04,
        minScale: 0.2,
        maxScale: 2.0,
        scrollActivationWidth: null,
        keyboard: {
          27: () => close(), // ESC to close
        },
        plugins: [],
      });

      await deck.initialize();
      revealInstanceRef.current = deck;

      // Setup zoom & pan for mermaid diagrams
      initMermaidZoomPan(deckRef.current);
    })();

    return () => {
      cancelled = true;
    };
  }, [isOpen, contentHtml, title, seriesName, lessonMeta, accentColor, close]);

  // ESC key listener
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, close]);

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={open}
        className="present-btn"
        title="进入演示模式 (PPT)"
        aria-label="进入演示模式"
        type="button"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
        </svg>
        <span className="present-btn__label">演示模式</span>
      </button>

      {/* Fullscreen overlay */}
      {isOpen && (
        <div className="reveal-overlay">
          {/* Close button */}
          <button
            onClick={close}
            className="reveal-close"
            title="退出演示 (ESC)"
            type="button"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          {/* reveal.js deck container */}
          <div className="reveal" ref={deckRef}>
            <div className="slides">
              {/* Slides injected by JS */}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ---------- Slide building logic ----------

function buildSlides(
  html: string,
  title: string,
  seriesName?: string,
  lessonMeta?: string,
  accentColor?: string,
): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html');
  const root = doc.body.firstElementChild!;

  // Flatten .tutorial-section wrappers injected by SectionReveal.
  // We need a flat list of block elements (h2, h3, p, pre, ul, etc.)
  const flatChildren: Element[] = [];
  for (const child of Array.from(root.children)) {
    if (child.tagName === 'SECTION' && child.classList.contains('tutorial-section')) {
      // Unwrap: add all children of this section
      for (const inner of Array.from(child.children)) {
        flatChildren.push(inner);
      }
    } else {
      flatChildren.push(child);
    }
  }

  // Filter out navigation/footer elements that shouldn't appear in presentation
  const filteredChildren = flatChildren.filter((el) => {
    const text = el.textContent || '';
    // Skip nav footer lines like "导航: ← xxx · ↑ index · xxx →"
    if (/导航\s*[:：]/.test(text) && /[←→↑]/.test(text)) return false;
    // Skip HTML comments rendered as empty elements
    if (!text.trim() && !el.querySelector('svg, img')) return false;
    // Skip <hr> at the very end (usually before nav)
    if (el.tagName === 'HR') return false;
    // Skip elements that are just "---" separators with no semantic value
    if (el.tagName === 'P' && /^\s*[-—]{3,}\s*$/.test(text)) return false;
    // Skip "最后更新" lines
    if (/最后更新/.test(text) && text.trim().length < 30) return false;
    return true;
  });

  const sections: string[] = [];

  // Title slide
  sections.push(`
    <section data-background-gradient="linear-gradient(135deg, #1a1d2e 0%, #0f1117 100%)">
      <div style="display:flex;flex-direction:column;align-items:center;gap:1rem;">
        ${seriesName ? `<span style="font-size:14px;padding:4px 12px;border-radius:999px;background:${accentColor}22;color:${accentColor};border:1px solid ${accentColor}44;font-weight:600;">${seriesName}</span>` : ''}
        <h2 style="font-size:2.4em;font-weight:800;color:#fff;line-height:1.2;margin:0;">${escHtml(title)}</h2>
        ${lessonMeta ? `<p style="font-size:0.85em;color:rgba(255,255,255,0.55);margin:0;">${escHtml(lessonMeta)}</p>` : ''}
        <p style="margin-top:2rem;font-size:0.7em;color:rgba(255,255,255,0.35);">← → 键翻页 · ESC 退出</p>
      </div>
    </section>
  `);

  // Walk through the flat content and build slides.
  // Strategy:
  //   - h2 / h3 always start a new slide
  //   - Code blocks, mermaid diagrams, and tables get their own dedicated slide
  //   - Lists and paragraphs accumulate on the current slide (max ~5 items per page)
  //   - Blockquotes become speaker notes for the current slide
  const MAX_ITEMS_PER_SLIDE = 5;

  let currentSlide: string[] = [];
  let currentNotes = '';
  let hasContent = false;
  let currentHeading = ''; // remembers last h2/h3 for context
  let itemCount = 0;

  const flushSlide = () => {
    if (!hasContent) return;
    let slideHtml = currentSlide.join('\n');
    if (currentNotes) {
      slideHtml += `<aside class="notes">${currentNotes}</aside>`;
    }
    sections.push(`<section data-background-color="#0f1117">${slideHtml}</section>`);
    currentSlide = [];
    currentNotes = '';
    hasContent = false;
    itemCount = 0;
  };

  // Check if we should auto-split
  const maybeFlush = () => {
    if (itemCount >= MAX_ITEMS_PER_SLIDE) {
      flushSlide();
      // Carry forward heading context so the new slide isn't bare
      if (currentHeading) {
        currentSlide.push(currentHeading);
        hasContent = true;
      }
    }
  };

  const children = filteredChildren;
  for (const el of children) {
    const tag = el.tagName.toLowerCase();

    // Skip hidden h1
    if (tag === 'h1') continue;

    // h2 → dedicated TITLE slide (centered, large font)
    if (tag === 'h2') {
      flushSlide();
      // H2 gets its own full-screen title slide with zoom transition
      sections.push(`
        <section data-background-color="#0f1117" data-transition="zoom">
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;">
            <h2 style="color:${accentColor};font-size:2.2em;font-weight:800;text-align:center;border:none;line-height:1.3;margin:0;">${el.innerHTML}</h2>
          </div>
        </section>
      `);
      // Store a smaller heading for content slides in this section
      currentHeading = `<h2 style="color:${accentColor};font-size:1.2em;font-weight:700;text-align:center;margin-bottom:0.6em;border:none;opacity:0.8;">${el.innerHTML}</h2>`;
      hasContent = false;
      continue;
    }

    // h3 → visual section divider within current slide (does NOT force a new page)
    if (tag === 'h3') {
      // Only flush if current slide already has content (avoid leaving h3 alone)
      if (itemCount >= 3) {
        flushSlide();
      }
      currentHeading = `<h3 style="color:#e2e8f0;font-size:1.3em;font-weight:700;text-align:center;margin:0.6em 0 0.3em;">${el.innerHTML}</h3>`;
      currentSlide.push(currentHeading);
      hasContent = true;
      itemCount++;
      continue;
    }

    // h4 - don't start new slide but add as sub-heading
    if (tag === 'h4' || tag === 'h5' || tag === 'h6') {
      maybeFlush();
      currentSlide.push(`<h4 class="fragment" style="color:#cbd5e1;font-size:1.1em;font-weight:600;text-align:center;margin:0.8em 0 0.3em;">${el.innerHTML}</h4>`);
      hasContent = true;
      itemCount++;
      continue;
    }

    // Blockquote → speaker notes
    if (tag === 'blockquote') {
      currentNotes += (el.textContent || '') + '\n';
      continue;
    }

    // Code blocks → dedicated slide with macOS window styling
    if (tag === 'pre' || (tag === 'div' && el.classList.contains('code-window'))) {
      flushSlide();
      const code = el.querySelector('code');
      const text = code?.textContent || el.textContent || '';
      const lines = text.trim().split('\n');
      const lang = el.getAttribute('data-language') || code?.className?.match(/language-(\w+)/)?.[1] || '';

      // Show ALL lines (container is scrollable)
      const numberedLines = lines.map((line, i) => {
        const num = String(i + 1).padStart(3, ' ');
        const highlighted = basicHighlight(line, lang);
        return `<span class="slide-code-line"><span class="slide-code-num">${num}</span>${highlighted}</span>`;
      });

      let slideHtml = '';
      if (currentHeading) slideHtml += currentHeading;
      slideHtml += `
        <div class="slide-code-window">
          <div class="slide-code-header">
            <span class="slide-code-dots">
              <i></i><i></i><i></i>
            </span>
            <span class="slide-code-lang">${lang.toUpperCase() || 'CODE'}</span>
            <span class="slide-code-info">${lines.length} 行</span>
          </div>
          <div class="slide-code-body">
            <pre><code>${numberedLines.join('\n')}</code></pre>
          </div>
        </div>
      `;
      sections.push(`<section data-background-color="#0f1117" data-transition="convex">${slideHtml}</section>`);
      hasContent = false;
      itemCount = 0;
      continue;
    }

    // Mermaid figures → dedicated full-page slide (no heading, just the diagram)
    if (
      (tag === 'figure' && (el.classList.contains('mermaid-figure') || el.classList.contains('mermaid-container'))) ||
      (tag === 'div' && el.classList.contains('mermaid-card'))
    ) {
      flushSlide();
      // IMPORTANT: target the diagram SVG specifically — `el.querySelector('svg')`
      // would pick up the small toggle-button icons inside `.mermaid-header`
      // (they appear earlier in DOM order), producing a huge "move" icon
      // instead of the actual chart. The real diagram lives inside
      // `.mermaid-body`.
      const body = el.querySelector('.mermaid-body');
      const svgEl = (body?.querySelector('svg') as SVGElement | null)
        ?? (el.querySelector('svg:not(.mermaid-mode-icon)') as SVGElement | null);
      const badge = el.querySelector('.mermaid-badge')?.textContent || 'DIAGRAM';

      // Clone the SVG so we can safely strip inline transforms that the
      // article-side zoom/pan handler may have left on it. Without this,
      // the SVG can render with a stale `transform: scale(...)` from the
      // article view and end up invisible inside the slide.
      let diagramHtml = '';
      if (svgEl) {
        const cloned = svgEl.cloneNode(true) as SVGElement;
        cloned.style.transform = '';
        cloned.style.transformOrigin = '';
        diagramHtml = cloned.outerHTML;
      } else {
        diagramHtml = body?.innerHTML || el.innerHTML;
      }

      const slideHtml = `
        <div class="slide-mermaid-window">
          <div class="slide-mermaid-header">
            <span class="slide-mermaid-dots"><i></i><i></i><i></i></span>
            <span class="slide-mermaid-badge">${escHtml(badge)}</span>
            <span class="slide-mermaid-hint">滚轮缩放 · 拖拽移动</span>
          </div>
          <div class="slide-mermaid-body slide-mermaid-zoomable" data-zoom="1" data-x="0" data-y="0">
            <div class="slide-mermaid-inner">${diagramHtml}</div>
          </div>
        </div>
      `;
      sections.push(`<section data-background-color="#0f1117" class="mermaid-slide">${slideHtml}</section>`);
      hasContent = false;
      itemCount = 0;
      continue;
    }

    // Tables → dedicated slide
    if (tag === 'table') {
      flushSlide();
      let slideHtml = '';
      if (currentHeading) slideHtml += currentHeading;
      slideHtml += `<div style="font-size:0.7em;overflow-x:auto;">${el.outerHTML}</div>`;
      sections.push(`<section data-background-color="#0f1117">${slideHtml}</section>`);
      hasContent = false;
      itemCount = 0;
      continue;
    }

    // Lists → each <li> is a fragment (entire list on one slide)
    if (tag === 'ul' || tag === 'ol') {
      maybeFlush();
      const listItems = Array.from(el.querySelectorAll(':scope > li'));
      // If list is long, it gets its own slide
      if (listItems.length > 6 && itemCount > 0) {
        flushSlide();
        if (currentHeading) {
          currentSlide.push(currentHeading);
          hasContent = true;
        }
      }
      const listTag = tag;
      let listHtml = `<${listTag} style="text-align:left;font-size:0.8em;line-height:1.9;color:#cbd5e1;padding-left:1.2em;display:inline-block;margin:0 auto;">`;
      listItems.forEach((li) => {
        listHtml += `<li class="fragment" style="margin-bottom:0.3em;">${li.innerHTML}</li>`;
      });
      listHtml += `</${listTag}>`;
      currentSlide.push(`<div style="text-align:center;">${listHtml}</div>`);
      hasContent = true;
      itemCount += Math.ceil(listItems.length / 2); // lists count as multiple items
      continue;
    }

    // Paragraphs
    if (tag === 'p') {
      maybeFlush();
      const text = el.textContent || '';
      // Skip very short empty-ish paragraphs
      if (text.trim().length < 3) continue;
      currentSlide.push(`<p class="fragment" style="text-align:center;font-size:0.8em;line-height:1.8;color:#94a3b8;margin:0.4em auto;max-width:90%;">${el.innerHTML}</p>`);
      hasContent = true;
      itemCount++;
      continue;
    }

    // <hr> — treat as section break
    if (tag === 'hr') {
      flushSlide();
      currentHeading = '';
      continue;
    }

    // div containers (e.g. code-window wrappers that weren't caught above)
    if (tag === 'div') {
      // Check if it contains a <pre> (code window)
      const innerPre = el.querySelector('pre');
      if (innerPre) {
        flushSlide();
        const code = innerPre.querySelector('code');
        const text = code?.textContent || innerPre.textContent || '';
        const lines = text.trim().split('\n');
        const lang = innerPre.getAttribute('data-language') || code?.className?.match(/language-(\w+)/)?.[1] || '';
        const displayLines = lines.slice(0, 20);
        const truncated = lines.length > 20 ? `\n// ... +${lines.length - 20} more lines` : '';
        let slideHtml = '';
        if (currentHeading) slideHtml += currentHeading;
        slideHtml += `<pre style="text-align:left;font-size:0.52em;line-height:1.6;background:#1a1d2e;border:1px solid #2e3348;border-radius:10px;padding:1.2em 1.4em;overflow-x:auto;max-width:100%;"><code style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;">${escHtml(displayLines.join('\n') + truncated)}</code></pre>`;
        slideHtml += `<p style="text-align:right;font-size:0.5em;color:rgba(255,255,255,0.35);margin:0.3em 0 0;">${lang.toUpperCase()} · ${lines.length} 行</p>`;
        sections.push(`<section data-background-color="#0f1117">${slideHtml}</section>`);
        hasContent = false;
        itemCount = 0;
        continue;
      }
      // Otherwise treat as a paragraph
      const text = el.textContent || '';
      if (text.trim().length > 5) {
        maybeFlush();
        currentSlide.push(`<div class="fragment" style="text-align:left;font-size:0.8em;line-height:1.8;color:#94a3b8;">${el.innerHTML}</div>`);
        hasContent = true;
        itemCount++;
      }
      continue;
    }

    // Catch-all for other elements
    if (el.outerHTML.trim() && (el.textContent || '').trim().length > 3) {
      maybeFlush();
      currentSlide.push(`<div class="fragment" style="text-align:left;font-size:0.8em;color:#94a3b8;">${el.outerHTML}</div>`);
      hasContent = true;
      itemCount++;
    }
  }

  flushSlide();

  // End slide
  sections.push(`
    <section data-background-gradient="linear-gradient(135deg, #1a1d2e 0%, #0f1117 100%)">
      <div style="display:flex;flex-direction:column;align-items:center;gap:1rem;">
        <h2 style="font-size:2.2em;color:#fff;margin:0;">🎉 完成</h2>
        <p style="color:rgba(255,255,255,0.6);font-size:0.9em;margin:0;">按 ESC 返回文档阅读模式</p>
      </div>
    </section>
  `);

  return sections.join('\n');
}

function escHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Basic syntax highlighting for slide code.
 *  Input: raw text line (NOT pre-escaped).
 *  Output: safe HTML with <span> color tags. */
function basicHighlight(rawLine: string, lang: string): string {
  // Tokenize the line into segments: highlighted spans vs plain text
  type Token = { text: string; color?: string; italic?: boolean };
  const tokens: Token[] = [];
  let remaining = rawLine;

  const l = lang.toLowerCase();
  const isCpp = ['cpp', 'c', 'c++', 'h', 'hpp', 'cxx'].includes(l);
  const isTS = ['ts', 'typescript', 'js', 'javascript', 'tsx', 'jsx'].includes(l);

  // Helper: consume a regex match from the front of `remaining`
  const tryMatch = (re: RegExp, color: string, italic = false): boolean => {
    const m = remaining.match(re);
    if (m && m.index === 0) {
      tokens.push({ text: m[0], color, italic });
      remaining = remaining.slice(m[0].length);
      return true;
    }
    return false;
  };

  while (remaining.length > 0) {
    // Comments
    if (tryMatch(/^\/\/.*/, '#6b7280', true)) continue;
    if (tryMatch(/^\/\*[\s\S]*?\*\//, '#6b7280', true)) continue;
    if (tryMatch(/^#.*/, '#6b7280', true)) continue;

    // Strings
    if (tryMatch(/^"[^"]*"/, '#a5d6ff')) continue;
    if (tryMatch(/^'[^']*'/, '#a5d6ff')) continue;

    // Numbers
    if (tryMatch(/^0x[0-9a-fA-F]+/, '#79c0ff')) continue;
    if (tryMatch(/^\d+\.?\d*f?/, '#79c0ff')) continue;

    // C++ keywords
    if (isCpp && tryMatch(/^(UCLASS|USTRUCT|UENUM|UPROPERTY|UFUNCTION|GENERATED_BODY|Super|class|struct|enum|void|int|float|double|bool|char|const|static|virtual|override|public|private|protected|return|if|else|for|while|do|switch|case|break|continue|new|delete|nullptr|true|false|this|auto|template|typename|namespace|using|typedef|inline|explicit|mutable|volatile|extern)\b/, '#ff7b72')) continue;

    // C++ UE types (starts with U, A, F, T + uppercase)
    if (isCpp && tryMatch(/^[UFAT][A-Z][A-Za-z0-9]*/, '#d2a8ff')) continue;

    // TS/JS keywords
    if (isTS && tryMatch(/^(const|let|var|function|class|interface|type|export|import|from|return|if|else|for|while|async|await|new|this|true|false|null|undefined|typeof|extends|implements)\b/, '#ff7b72')) continue;

    // Identifiers followed by ( → function call
    if (tryMatch(/^[A-Za-z_]\w*(?=\()/, '#d2a8ff')) continue;

    // Plain identifier (no color)
    if (tryMatch(/^[A-Za-z_]\w*/, undefined)) continue;

    // Operators and punctuation (no color, just advance)
    tokens.push({ text: remaining[0] });
    remaining = remaining.slice(1);
  }

  // Build HTML
  return tokens
    .map((t) => {
      const safe = escHtml(t.text);
      if (t.color) {
        const style = `color:${t.color};${t.italic ? 'font-style:italic;' : ''}`;
        return `<span style="${style}">${safe}</span>`;
      }
      return safe;
    })
    .join('');
}

/** Initialize mouse wheel zoom + drag pan on all `.slide-mermaid-zoomable` containers */
function initMermaidZoomPan(root: HTMLElement) {
  const containers = root.querySelectorAll<HTMLElement>('.slide-mermaid-zoomable');

  containers.forEach((container) => {
    const inner = container.querySelector<HTMLElement>('.slide-mermaid-inner');
    if (!inner) return;

    let scale = 1;
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let startX = 0;
    let startY = 0;

    const applyTransform = () => {
      inner.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
    };

    // Wheel → zoom
    container.addEventListener('wheel', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      scale = Math.max(0.3, Math.min(4, scale + delta));
      applyTransform();
    }, { passive: false });

    // Mouse drag → pan
    container.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return; // left click only
      isDragging = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
      container.style.cursor = 'grabbing';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      panX = e.clientX - startX;
      panY = e.clientY - startY;
      applyTransform();
    });

    document.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        container.style.cursor = 'grab';
      }
    });

    // Double-click → reset
    container.addEventListener('dblclick', (e) => {
      e.preventDefault();
      scale = 1;
      panX = 0;
      panY = 0;
      applyTransform();
    });

    // Initial cursor
    container.style.cursor = 'grab';
  });
}
