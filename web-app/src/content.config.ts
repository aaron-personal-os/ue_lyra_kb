import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const tutorials = defineCollection({
  loader: glob({
    pattern: '**/*.md',
    base: '../Docs/30-tutorials',
    // Let Astro generate entry IDs from file paths; ignore frontmatter `id` field.
    generateId: ({ entry }) => entry.replace(/\.md$/, ''),
  }),
  schema: z.object({
    title: z.string().optional(),
    description: z.string().optional(),
    type: z.string().optional(),
    status: z.string().optional(),
    language: z.string().optional(),
    owner: z.string().optional(),
    series: z.string().optional(),
    lesson_index: z.number().optional(),
    difficulty: z.string().optional(),
    prerequisites: z.array(z.any()).nullable().optional(),
    engine_sources: z.array(z.any()).nullable().optional(),
    lyra_sources: z.array(z.any()).nullable().optional(),
    tags: z.array(z.string()).nullable().optional(),
    last_synced: z.union([z.string(), z.date()]).nullable().optional(),
    last_verified: z.union([z.string(), z.date()]).nullable().optional(),
    related: z.array(z.any()).nullable().optional(),
    sources: z.array(z.any()).nullable().optional(),
    anchors: z.array(z.any()).nullable().optional(),
  }).passthrough(),
});

export const collections = { tutorials };
