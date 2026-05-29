/**
 * {{module}} — Utility Library
 *
 * Purpose: {{description}}
 * Location: src/lib/{{module}}.ts
 *
 * Conventions:
 *   - Pure functions (no side effects unless explicitly noted)
 *   - camelCase function names
 *   - Interface before implementation
 *   - Export at bottom or inline
 */

import fs from 'node:fs';
import path from 'node:path';
import yaml from 'yaml';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ItemMeta {
  /** Unique identifier */
  id: string;
  /** Display name */
  name: string;
  /** Optional description */
  description?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DOCS_ROOT = path.resolve(
  path.dirname(new URL(import.meta.url).pathname),
  '../../../Docs'
);

// ─── Core Functions ───────────────────────────────────────────────────────────

/**
 * Get all items from a YAML config file.
 * Runs at build time (server-side only).
 */
export async function getAllItems(): Promise<ItemMeta[]> {
  const configPath = path.join(DOCS_ROOT, 'config.yaml');
  if (!fs.existsSync(configPath)) return [];

  const raw = fs.readFileSync(configPath, 'utf-8');
  const parsed = yaml.parse(raw);
  return parsed.items ?? [];
}

/**
 * Get a single item by ID.
 */
export async function getItemById(id: string): Promise<ItemMeta | undefined> {
  const all = await getAllItems();
  return all.find((item) => item.id === id);
}

// ─── Helper Functions (internal) ──────────────────────────────────────────────

/**
 * Humanize a slug into a title.
 * "my-cool-thing" → "My Cool Thing"
 */
function humanize(slug: string): string {
  return slug
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ─── Client-side utilities (if needed) ────────────────────────────────────────

// For functions that run in the browser, guard with typeof window check:
//
// export function getStoredValue(key: string): string | null {
//   if (typeof window === 'undefined') return null;
//   return localStorage.getItem(key);
// }
