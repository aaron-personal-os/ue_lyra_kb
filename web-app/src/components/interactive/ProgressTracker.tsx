import { useEffect } from 'react';
import { markLessonComplete, getSeriesProgressPercent } from '../../lib/progress';

interface Props {
  seriesSlug: string;
  lessonId: string;
  totalLessons: number;
}

export default function ProgressTracker({ seriesSlug, lessonId, totalLessons }: Props) {
  useEffect(() => {
    if (!lessonId) return;

    markLessonComplete(seriesSlug, lessonId);
    const percent = getSeriesProgressPercent(seriesSlug, totalLessons);

    // Update sidebar progress bar if it exists
    const bar = document.getElementById('series-progress-bar');
    const text = document.getElementById('series-progress-text');
    if (bar) bar.style.width = `${percent}%`;
    if (text) text.textContent = `${percent}% complete`;
  }, [seriesSlug, lessonId, totalLessons]);

  // Invisible component — just triggers the side effect
  return null;
}
