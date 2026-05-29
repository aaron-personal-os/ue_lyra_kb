import { useState } from 'react';
import { motion } from 'framer-motion';

interface QuizOption {
  label: string;
  value: string;
}

interface Props {
  question: string;
  options: QuizOption[];
  answer: string;
  explanation?: string;
}

export default function Quiz({ question, options, answer, explanation }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const isCorrect = selected === answer;

  const handleSubmit = () => {
    if (selected) {
      setSubmitted(true);
    }
  };

  const handleReset = () => {
    setSelected(null);
    setSubmitted(false);
  };

  const getOptionClasses = (value: string) => {
    const base =
      'w-full text-left px-4 py-3 rounded-lg border text-sm transition-all duration-200';

    if (!submitted) {
      if (value === selected) {
        return `${base} border-[var(--accent)]/50 bg-[var(--accent)]/5 text-[var(--text-primary)]`;
      }
      return `${base} border-white/[0.08] text-[var(--text-secondary)] hover:border-white/20 hover:text-[var(--text-primary)]`;
    }

    // After submission
    if (value === answer) {
      return `${base} border-emerald-500/50 bg-emerald-500/10 text-emerald-300`;
    }
    if (value === selected && value !== answer) {
      return `${base} border-red-500/50 bg-red-500/10 text-red-300`;
    }
    return `${base} border-white/[0.08] text-[var(--text-secondary)] opacity-50`;
  };

  return (
    <div className="my-6 rounded-xl border border-white/[0.08] overflow-hidden bg-[var(--surface-1)]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.08] bg-white/[0.02]">
        <span className="text-sm font-medium text-[var(--text-primary)]">📝 Quiz</span>
      </div>

      {/* Question */}
      <div className="px-4 pt-4 pb-2">
        <p className="text-sm font-medium text-[var(--text-primary)]">{question}</p>
      </div>

      {/* Options */}
      <div className="px-4 py-2 space-y-2">
        {options.map((option) => (
          <button
            key={option.value}
            onClick={() => !submitted && setSelected(option.value)}
            disabled={submitted}
            className={getOptionClasses(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Actions */}
      <div className="px-4 py-3">
        {!submitted ? (
          <button
            onClick={handleSubmit}
            disabled={!selected}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity disabled:opacity-30 disabled:pointer-events-none"
          >
            Check Answer
          </button>
        ) : (
          <button
            onClick={handleReset}
            className="px-4 py-2 text-xs font-medium rounded-lg border border-white/[0.08] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/[0.05] transition-colors"
          >
            Try Again
          </button>
        )}
      </div>

      {/* Feedback */}
      {submitted && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className={`mx-4 mb-4 p-3 rounded-lg border ${
            isCorrect
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : 'border-red-500/30 bg-red-500/5'
          }`}
        >
          <div className={`text-sm font-medium mb-1 ${isCorrect ? 'text-emerald-400' : 'text-red-400'}`}>
            {isCorrect ? '✅ 正确!' : '❌ 错误'}
          </div>
          {explanation && (
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {explanation}
            </p>
          )}
        </motion.div>
      )}
    </div>
  );
}
