import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Step {
  label: string;
  description: string;
}

interface Props {
  title?: string;
  steps: Step[];
}

export default function StepAnimation({ title = '🎬 Step Animation', steps }: Props) {
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(1);

  const isFirst = current === 0;
  const isLast = current === steps.length - 1;

  const goTo = (index: number) => {
    setDirection(index > current ? 1 : -1);
    setCurrent(index);
  };

  const prev = () => {
    if (!isFirst) goTo(current - 1);
  };

  const next = () => {
    if (!isLast) goTo(current + 1);
  };

  const replay = () => {
    setDirection(-1);
    setCurrent(0);
  };

  const variants = {
    enter: (dir: number) => ({
      x: dir > 0 ? 40 : -40,
      opacity: 0,
    }),
    center: {
      x: 0,
      opacity: 1,
    },
    exit: (dir: number) => ({
      x: dir > 0 ? -40 : 40,
      opacity: 0,
    }),
  };

  return (
    <div className="my-6 rounded-xl border border-white/[0.08] overflow-hidden bg-[var(--surface-1)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08] bg-white/[0.02]">
        <span className="text-sm font-medium text-[var(--text-primary)]">{title}</span>
        <span className="text-xs text-[var(--text-secondary)]">
          {current + 1} / {steps.length}
        </span>
      </div>

      {/* Content area */}
      <div className="relative min-h-[160px] flex items-center justify-center px-6 py-8 overflow-hidden">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={current}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="text-center"
          >
            <div className="text-lg font-semibold text-[var(--accent)] mb-2">
              {steps[current].label}
            </div>
            <div className="text-sm text-[var(--text-secondary)] max-w-md">
              {steps[current].description}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Progress dots */}
      <div className="flex items-center justify-center gap-1.5 py-3">
        {steps.map((_, i) => (
          <button
            key={i}
            onClick={() => goTo(i)}
            className={`w-2 h-2 rounded-full transition-all duration-200 ${
              i === current
                ? 'bg-[var(--accent)] scale-125'
                : 'bg-white/20 hover:bg-white/40'
            }`}
            aria-label={`Go to step ${i + 1}`}
          />
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-2 px-4 py-3 border-t border-white/[0.08]">
        <button
          onClick={prev}
          disabled={isFirst}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-white/[0.08] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.05] transition-colors disabled:opacity-30 disabled:pointer-events-none"
        >
          ◀ Prev
        </button>
        <button
          onClick={next}
          disabled={isLast}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-white/[0.08] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.05] transition-colors disabled:opacity-30 disabled:pointer-events-none"
        >
          Next ▶
        </button>
        <button
          onClick={replay}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-white/[0.08] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.05] transition-colors"
        >
          ⟳ Replay
        </button>
      </div>
    </div>
  );
}
