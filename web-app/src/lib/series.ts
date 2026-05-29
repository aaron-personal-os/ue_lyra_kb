import fs from 'node:fs';
import path from 'node:path';
import yaml from 'yaml';

export interface SeriesStage {
  stage: string;
  description?: string;
  lessons: string[];
}

export interface SeriesPrerequisite {
  series?: string;
  minimum?: string;
  concept?: string;
  description?: string;
}

export interface SeriesMeta {
  name: string;
  slug: string;
  description: string;
  difficulty_range?: string[] | string;
  ue_version?: string;
  total_lessons: number;
  estimated_hours: number;
  prerequisites?: SeriesPrerequisite[];
  learning_path: SeriesStage[];
  tags?: string[];
}

const TUTORIALS_DIR = path.resolve(process.cwd(), '../Docs/30-tutorials');

export function getAllSeries(): SeriesMeta[] {
  const dirs = fs.readdirSync(TUTORIALS_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory());

  const seriesList: SeriesMeta[] = [];

  for (const dir of dirs) {
    const yamlPath = path.join(TUTORIALS_DIR, dir.name, '_series.yaml');
    if (fs.existsSync(yamlPath)) {
      const content = fs.readFileSync(yamlPath, 'utf-8');
      const parsed = yaml.parse(content);

      // Normalize learning_path: support flat `lessons:` as a single stage fallback
      let learningPath: SeriesStage[] = Array.isArray(parsed.learning_path)
        ? parsed.learning_path
        : [];
      if (learningPath.length === 0 && Array.isArray(parsed.lessons)) {
        learningPath = [
          {
            stage: parsed.stage || '教程目录',
            description: parsed.stage_description,
            lessons: parsed.lessons.filter((x: unknown) => typeof x === 'string'),
          },
        ];
      }

      const computedTotal = learningPath.reduce(
        (sum, s) => sum + (Array.isArray(s.lessons) ? s.lessons.length : 0),
        0,
      );

      seriesList.push({
        name: parsed.name || parsed.title || dir.name,
        slug: parsed.slug || parsed.id || dir.name,
        description: parsed.description || '',
        difficulty_range: parsed.difficulty_range || parsed.difficulty || 'intermediate',
        ue_version: parsed.ue_version,
        total_lessons: parsed.total_lessons || computedTotal,
        estimated_hours: parsed.estimated_hours || 0,
        prerequisites: parsed.prerequisites,
        learning_path: learningPath,
        tags: parsed.tags,
      });
    }
  }

  return seriesList;
}

export function getSeriesBySlug(slug: string): SeriesMeta | undefined {
  return getAllSeries().find(s => s.slug === slug);
}

export function getSeriesLessons(slug: string): string[] {
  const series = getSeriesBySlug(slug);
  if (!series) return [];
  return series.learning_path.flatMap(stage => stage.lessons);
}

export function getLessonTitle(seriesSlug: string, lessonFile: string): string {
  return getLessonMeta(seriesSlug, lessonFile).title;
}

export interface LessonMeta {
  title: string;
  summary: string;
  difficulty?: string;
  estimatedMinutes?: number;
}

export function getLessonMeta(seriesSlug: string, lessonFile: string): LessonMeta {
  const mdPath = path.join(TUTORIALS_DIR, seriesSlug, `${lessonFile}.md`);
  if (!fs.existsSync(mdPath)) {
    return { title: humanize(lessonFile), summary: '' };
  }

  const content = fs.readFileSync(mdPath, 'utf-8');
  const fm = extractFrontmatter(content);
  const body = stripFrontmatter(content);

  // Title: frontmatter title, then first H1, then humanized filename
  let title = '';
  if (fm) {
    const t = fm.match(/^title:\s*(.+)$/m);
    if (t && t[1]) title = cleanupTitle(stripQuotes(t[1].trim()));
  }
  if (!title) {
    const h1 = body.match(/^[ \t]*#[ \t]+(.+?)\s*$/m);
    if (h1 && h1[1]) title = cleanupTitle(h1[1]);
  }
  if (!title) title = humanize(lessonFile);

  // Summary: prioritize frontmatter description field
  let summary = '';
  if (fm) {
    const desc = fm.match(/^description:\s*(.+)$/m);
    if (desc && desc[1]) {
      summary = cleanupTitle(stripQuotes(desc[1].trim()));
    }
  }
  // Fallback: first blockquote after H1
  if (!summary) {
    const h1 = body.match(/^[ \t]*#[ \t]+(.+?)\s*$/m);
    const afterH1 = h1 ? body.slice(body.indexOf(h1[0]) + h1[0].length) : body;
    const bq = afterH1.match(/^[ \t]*>[ \t]?(.+?)\s*$/m);
    if (bq && bq[1]) {
      summary = cleanupTitle(bq[1]);
    }
  }
  // Strip simple markdown emphasis to keep it clean
  summary = summary
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_m, _p1, p2) => p2 || _p1);

  // Optional metadata from frontmatter
  let difficulty: string | undefined;
  let estimatedMinutes: number | undefined;
  if (fm) {
    const d = fm.match(/^difficulty:\s*(.+)$/m);
    if (d && d[1]) difficulty = stripQuotes(d[1].trim());
    const e = fm.match(/^estimated_minutes:\s*(\d+)/m);
    if (e && e[1]) estimatedMinutes = Number(e[1]);
  }

  return { title, summary, difficulty, estimatedMinutes };
}

function extractFrontmatter(content: string): string | null {
  if (!content.startsWith('---')) return null;
  const end = content.indexOf('\n---', 3);
  if (end === -1) return null;
  return content.slice(3, end);
}

function stripFrontmatter(content: string): string {
  if (!content.startsWith('---')) return content;
  const end = content.indexOf('\n---', 3);
  if (end === -1) return content;
  return content.slice(end + 4);
}

function stripQuotes(value: string): string {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function cleanupTitle(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

function humanize(filename: string): string {
  return filename
    .replace(/^\d+-/, '')
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
