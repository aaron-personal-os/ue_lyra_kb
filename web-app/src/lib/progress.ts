const STORAGE_KEY = 'lyra-kb-progress';

export interface SeriesProgress {
  completedLessons: string[];
  lastVisited: string | null;
  lastVisitedAt: number;
}

export function getProgress(seriesSlug: string): SeriesProgress {
  if (typeof window === 'undefined') {
    return { completedLessons: [], lastVisited: null, lastVisitedAt: 0 };
  }
  const all = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  return all[seriesSlug] || { completedLessons: [], lastVisited: null, lastVisitedAt: 0 };
}

export function markLessonComplete(seriesSlug: string, lessonId: string): void {
  if (typeof window === 'undefined') return;
  const all = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  const series = all[seriesSlug] || { completedLessons: [], lastVisited: null, lastVisitedAt: 0 };

  if (!series.completedLessons.includes(lessonId)) {
    series.completedLessons.push(lessonId);
  }
  series.lastVisited = lessonId;
  series.lastVisitedAt = Date.now();

  all[seriesSlug] = series;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}

export function getSeriesProgressPercent(seriesSlug: string, totalLessons: number): number {
  const progress = getProgress(seriesSlug);
  if (totalLessons === 0) return 0;
  return Math.round((progress.completedLessons.length / totalLessons) * 100);
}
