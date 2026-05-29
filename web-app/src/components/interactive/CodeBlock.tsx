import { useState } from 'react';

interface Props {
  code: string;
  language?: string;
  filename?: string;
  maxLines?: number;
}

export default function CodeBlock({ code, language = 'cpp', filename, maxLines = 15 }: Props) {
  const lines = code.split('\n');
  const isLong = lines.length > maxLines;
  const [expanded, setExpanded] = useState(!isLong);

  const displayedCode = expanded ? code : lines.slice(0, maxLines).join('\n');

  return (
    <div className="my-6 rounded-lg border border-white/[0.08] overflow-hidden bg-[var(--surface-1)]">
      {/* Header with filename and language */}
      {filename && (
        <div className="flex items-center justify-between px-4 py-2 bg-white/[0.02] border-b border-white/[0.08]">
          <span className="text-xs font-mono text-[var(--text-secondary)]">{filename}</span>
          <span className="text-xs text-[var(--text-secondary)]">{language}</span>
        </div>
      )}

      {/* Code content */}
      <div className="relative">
        <pre className="p-4 overflow-x-auto text-sm leading-relaxed">
          <code>{displayedCode}</code>
        </pre>

        {/* Show more button with gradient overlay */}
        {isLong && !expanded && (
          <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-[var(--surface-1)] to-transparent flex items-end justify-center pb-3">
            <button
              onClick={() => setExpanded(true)}
              className="px-4 py-1.5 text-xs font-medium bg-white/10 hover:bg-white/15 rounded-full text-white/70 hover:text-white transition-colors"
            >
              Show all {lines.length} lines ↓
            </button>
          </div>
        )}

        {/* Collapse button */}
        {isLong && expanded && (
          <div className="flex justify-center py-2 border-t border-white/[0.08]">
            <button
              onClick={() => setExpanded(false)}
              className="px-4 py-1.5 text-xs font-medium bg-white/10 hover:bg-white/15 rounded-full text-white/70 hover:text-white transition-colors"
            >
              Collapse ↑
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
