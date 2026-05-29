export interface SeriesTheme {
  gradient: string;
  badge: string;
  accent: string;
}

const themes: Record<string, SeriesTheme> = {
  gas: {
    gradient: 'from-indigo-950 via-indigo-900 to-violet-800',
    badge: 'bg-indigo-500/20 text-indigo-300',
    accent: '#818cf8',
  },
  'input-system': {
    gradient: 'from-emerald-950 via-emerald-900 to-teal-800',
    badge: 'bg-emerald-500/20 text-emerald-300',
    accent: '#6ee7b7',
  },
  'ai-behavior': {
    gradient: 'from-amber-950 via-amber-900 to-orange-800',
    badge: 'bg-amber-500/20 text-amber-300',
    accent: '#fbbf24',
  },
  animation: {
    gradient: 'from-pink-950 via-pink-900 to-rose-800',
    badge: 'bg-pink-500/20 text-pink-300',
    accent: '#f472b6',
  },
  niagara: {
    gradient: 'from-cyan-950 via-cyan-900 to-sky-800',
    badge: 'bg-cyan-500/20 text-cyan-300',
    accent: '#22d3ee',
  },
  pcg: {
    gradient: 'from-purple-950 via-purple-900 to-fuchsia-800',
    badge: 'bg-purple-500/20 text-purple-300',
    accent: '#a78bfa',
  },
  'ue-framework': {
    gradient: 'from-slate-900 via-slate-800 to-zinc-700',
    badge: 'bg-slate-500/20 text-slate-300',
    accent: '#94a3b8',
  },
  'network-sync': {
    gradient: 'from-blue-950 via-blue-900 to-sky-800',
    badge: 'bg-blue-500/20 text-blue-300',
    accent: '#60a5fa',
  },
  'game-feature': {
    gradient: 'from-lime-950 via-lime-900 to-green-800',
    badge: 'bg-lime-500/20 text-lime-300',
    accent: '#a3e635',
  },
  'modular-gameplay': {
    gradient: 'from-teal-950 via-teal-900 to-cyan-800',
    badge: 'bg-teal-500/20 text-teal-300',
    accent: '#2dd4bf',
  },
  'garbage-collection': {
    gradient: 'from-red-950 via-red-900 to-orange-800',
    badge: 'bg-red-500/20 text-red-300',
    accent: '#f87171',
  },
  'performance-optimization': {
    gradient: 'from-yellow-950 via-yellow-900 to-amber-800',
    badge: 'bg-yellow-500/20 text-yellow-300',
    accent: '#facc15',
  },
  'resource-management': {
    gradient: 'from-stone-900 via-stone-800 to-neutral-700',
    badge: 'bg-stone-500/20 text-stone-300',
    accent: '#a8a29e',
  },
  'localization-i18n': {
    gradient: 'from-sky-950 via-sky-900 to-blue-800',
    badge: 'bg-sky-500/20 text-sky-300',
    accent: '#38bdf8',
  },
  'lyra-practical': {
    gradient: 'from-violet-950 via-violet-900 to-purple-800',
    badge: 'bg-violet-500/20 text-violet-300',
    accent: '#a78bfa',
  },
};

const defaultTheme: SeriesTheme = {
  gradient: 'from-slate-900 via-slate-800 to-zinc-700',
  badge: 'bg-slate-500/20 text-slate-300',
  accent: '#94a3b8',
};

export function getSeriesTheme(slug: string): SeriesTheme {
  return themes[slug] || defaultTheme;
}
