import { useEffect, useState } from 'react';
import mermaid from 'mermaid';

interface Props {
  chart: string;
  caption?: string;
}

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    darkMode: true,
    background: '#1a1a24',
    primaryColor: '#6366f1',
    primaryTextColor: '#e2e8f0',
    primaryBorderColor: '#4f46e5',
    lineColor: '#94a3b8',
    secondaryColor: '#312e81',
    tertiaryColor: '#1e1b4b',
  },
});

export default function MermaidDiagram({ chart, caption }: Props) {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const renderChart = async () => {
      try {
        const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
        const { svg } = await mermaid.render(id, chart);
        setSvg(svg);
      } catch (e) {
        setError((e as Error).message);
      }
    };
    renderChart();
  }, [chart]);

  if (error) {
    return (
      <div className="my-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
        Mermaid render error: {error}
      </div>
    );
  }

  return (
    <figure className="my-6">
      <div
        className="p-6 rounded-lg bg-[var(--surface-1)] border border-white/[0.08] overflow-x-auto flex justify-center"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      {caption && (
        <figcaption className="text-center text-sm text-[var(--text-secondary)] mt-2">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
