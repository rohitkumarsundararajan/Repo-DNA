import { CYCLES, EDGES, FILES, LAYERS, SCORES, VIOLATIONS } from '../data/demo';
import type { FileNode, Job } from '../types';

export const BY_ID: Record<string, FileNode> = Object.fromEntries(FILES.map(f => [f.id, f]));
export const layerIdx = (id: string) => LAYERS.findIndex(l => l.id === id);
export const fname = (f: FileNode) => f.path.split('/').pop() ?? f.path;
export const fmt = (n: number) => n.toLocaleString('en-US');

export const uuid = (): string =>
  crypto.randomUUID
    ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 3) | 8).toString(16);
      });

/* ---------- repo URL validation ---------- */
const URL_RE = /^https:\/\/(www\.)?(github\.com|gitlab\.com)\/[\w.-]+\/[\w.-]+(\.git)?\/?$/i;

export function checkUrl(v: string): string {
  if (!v) return 'Paste a repo link to start.';
  if (!URL_RE.test(v)) return 'Use a public https link from GitHub or GitLab, like https://github.com/owner/repo.';
  return '';
}

export function repoName(url: string): string {
  return url
    .replace(/^https:\/\/(www\.)?/i, '')
    .replace(/\.git$/i, '')
    .replace(/\/$/, '')
    .split('/')
    .slice(1, 3)
    .join('/');
}

/* ---------- derived sets used by the diagram and issue lists ---------- */
export const violKey = new Set(VIOLATIONS.map(v => v.from + '>' + v.to));

export const cycleKey = new Set<string>();
CYCLES.forEach(c => c.nodes.forEach((n, i) => cycleKey.add(n + '>' + c.nodes[(i + 1) % c.nodes.length])));

export const inCycle = new Set(CYCLES.flatMap(c => c.nodes));
export const inViol = new Set(VIOLATIONS.flatMap(v => [v.from, v.to]));

export function evidence(): string[] {
  const down = EDGES.filter(
    ([a, b]) => !violKey.has(a + '>' + b) && layerIdx(BY_ID[a].layer) < layerIdx(BY_ID[b].layer),
  ).length;
  return [
    'Folders routes/, services/, repos/ and models/ line up with four layers',
    `${down} of ${EDGES.length} imports point down one layer, as a layered design expects`,
    `${VIOLATIONS.length} imports break the layer rules`,
  ];
}

export function totals() {
  return { loc: FILES.reduce((a, f) => a + f.loc, 0), files: FILES.length };
}

/* The full result JSON the worker sends back (contract shape) */
export function buildResultJson(job: Job) {
  const langs: Record<string, { name: string; files: number; loc: number }> = {};
  FILES.forEach(f => {
    langs[f.lang] = langs[f.lang] || { name: f.lang, files: 0, loc: 0 };
    langs[f.lang].files++;
    langs[f.lang].loc += f.loc;
  });
  return {
    schema_version: '1.0.0',
    job_id: job.id,
    repo_meta: { url: job.url || 'https://github.com/' + job.name, commit: 'a41f9c2', branch: 'main' },
    languages: Object.values(langs),
    frameworks: ['Express', 'Jest'],
    files: FILES.map(f => ({ path: f.path, loc: f.loc, cyclomatic: f.cyc, cognitive: f.cog, max_nesting: f.nest })),
    graph: {
      nodes: FILES.map(f => ({ id: f.path, layer: f.layer })),
      edges: EDGES.map(([a, b]) => ({ from: BY_ID[a].path, to: BY_ID[b].path })),
    },
    cycles: CYCLES.map(c => c.nodes.map(n => BY_ID[n].path)),
    architecture: {
      pattern: 'layered',
      evidence: evidence(),
      violations: VIOLATIONS.map(v => ({ from: BY_ID[v.from].path, to: BY_ID[v.to].path, rule: v.rule })),
    },
    scores: {
      architecture_dna: SCORES.architecture.value,
      code_dna: SCORES.code.value,
      quality_dna: SCORES.quality.value,
    },
  };
}
