import type { Cycle, Edge, FileNode, LayerId, Score, ScoreKey, Violation } from '../types';
import { CYCLES, EDGES, FILES, LAYERS, SCORES, VIOLATIONS } from '../data/demo';
import { BY_ID, cycleKey, evidence, inCycle, inViol, totals, violKey } from './utils';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '';

export interface AuthResponse {
  token: string;
  tokenType: string;
  expiresInSeconds: number;
}

export interface ApiJobResponse {
  job_id: string;
  status: 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED';
  source_type: 'git' | 'zip';
  repo_url: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface BackendAnalysisResult {
  schema_version: string;
  job_id: string;
  repo_meta: {
    repo_url: string | null;
    source_type: 'git' | 'zip';
    total_files: number;
    total_loc: number;
    analyzed_at?: string;
  };
  languages: Array<{
    name: string;
    file_count: number;
    loc: number;
    percentage: number;
  }>;
  frameworks: Array<{
    name: string;
    category?: string;
  }>;
  files: Array<{
    path: string;
    loc: number;
    cyclomatic: number;
    cognitive: number;
    max_nesting: number;
  }>;
  hotspots?: Array<{
    path: string;
    metric: string;
    value: number;
  }>;
  graph: {
    nodes: Array<{
      path: string;
      language?: string;
      folder?: string;
      fan_in?: number;
      fan_out?: number;
    }>;
    edges: Array<{
      from: string;
      to: string;
    }>;
  };
  cycles: string[][];
  architecture: {
    pattern: string;
    evidence: string[];
    violations: Array<{
      from: string;
      to: string;
      rule: string;
    }>;
  };
  scores: {
    architecture_dna: number;
    code_dna: number;
    quality_dna: number;
  };
}

export interface ResultViewModel {
  files: FileNode[];
  byId: Record<string, FileNode>;
  edges: Edge[];
  cycles: Cycle[];
  violations: Violation[];
  scores: Record<ScoreKey, Score>;
  languages: Record<string, number>;
  frameworks: string[];
  pattern: string;
  evidence: string[];
  rawResult: any;
  totals: { loc: number; files: number };
  violKey: Set<string>;
  cycleKey: Set<string>;
  inCycle: Set<string>;
  inViol: Set<string>;
}

/* Local authentication token management */
const TOKEN_KEY = 'repodna_token';
const USER_KEY = 'repodna_user';

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getUser(): string | null {
  try {
    return localStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
}

export function setAuth(token: string | null, user: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);

    if (user) localStorage.setItem(USER_KEY, user);
    else localStorage.removeItem(USER_KEY);
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function logout(): void {
  setAuth(null, null);
}

/* Helper to parse API responses and differentiate backend offline / proxy errors */
async function handleResponse<T>(res: Response, fallbackPrefix: string): Promise<T> {
  const contentType = res.headers.get('content-type') || '';
  if (res.ok) {
    if (contentType.includes('application/json')) {
      return res.json();
    }
    return (null as unknown) as T;
  }

  if (contentType.includes('application/json')) {
    const err = await res.json().catch(() => null);
    const msg =
      err?.message ||
      (err?.fieldErrors && err.fieldErrors[0]?.message) ||
      err?.error ||
      `${fallbackPrefix} failed (HTTP ${res.status})`;
    const error = new Error(msg);
    (error as any).status = res.status;
    throw error;
  }

  // Non-JSON responses on 500 / 502 / 503 / 504 are Vite proxy errors when backend is not listening
  if (res.status === 500 || res.status === 502 || res.status === 503 || res.status === 504) {
    const error = new Error('Backend server is not running on port 8080');
    (error as any).isBackendOffline = true;
    (error as any).status = res.status;
    throw error;
  }

  throw new Error(`${fallbackPrefix} failed (HTTP ${res.status})`);
}

/* API Calls */

export async function login(email: string, pw: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password: pw }),
    });
    const data = await handleResponse<AuthResponse>(res, 'Login');
    setAuth(data.token, email.trim());
    return data;
  } catch (err: any) {
    if (err.isBackendOffline || err.name === 'TypeError') {
      const offlineErr = new Error('Backend server is not running on port 8080');
      (offlineErr as any).isBackendOffline = true;
      throw offlineErr;
    }
    throw err;
  }
}

export async function register(email: string, pw: string): Promise<AuthResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password: pw }),
    });
    const data = await handleResponse<AuthResponse>(res, 'Registration');
    setAuth(data.token, email.trim());
    return data;
  } catch (err: any) {
    if (err.isBackendOffline || err.name === 'TypeError') {
      const offlineErr = new Error('Backend server is not running on port 8080');
      (offlineErr as any).isBackendOffline = true;
      throw offlineErr;
    }
    throw err;
  }
}

export async function submitRepo(repoUrl: string): Promise<{ jobId: string }> {
  const token = getToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const res = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ repo_url: repoUrl.trim() }),
    });
    const data = await handleResponse<{ job_id: string }>(res, 'Job submission');
    return { jobId: data.job_id };
  } catch (err: any) {
    if (err.isBackendOffline || err.name === 'TypeError') {
      const offlineErr = new Error('Backend server is not running on port 8080');
      (offlineErr as any).isBackendOffline = true;
      throw offlineErr;
    }
    throw err;
  }
}

export async function submitZip(file: File): Promise<{ jobId: string }> {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);

  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const res = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      headers,
      body: formData,
    });
    const data = await handleResponse<{ job_id: string }>(res, 'ZIP submission');
    return { jobId: data.job_id };
  } catch (err: any) {
    if (err.isBackendOffline || err.name === 'TypeError') {
      const offlineErr = new Error('Backend server is not running on port 8080');
      (offlineErr as any).isBackendOffline = true;
      throw offlineErr;
    }
    throw err;
  }
}

export async function getJobs(): Promise<ApiJobResponse[]> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/jobs`, { headers });
  return handleResponse<ApiJobResponse[]>(res, 'Fetch jobs');
}

export async function getJob(jobId: string): Promise<ApiJobResponse> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/jobs/${jobId}`, { headers });
  return handleResponse<ApiJobResponse>(res, 'Fetch job');
}

export async function getResult(jobId: string): Promise<BackendAnalysisResult> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/jobs/${jobId}/result`, { headers });
  return handleResponse<BackendAnalysisResult>(res, 'Fetch result');
}

export async function getDashboard(jobId: string): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/jobs/${jobId}/dashboard`, { headers });
  return handleResponse<any>(res, 'Fetch dashboard');
}

/* Helper to classify layer by file path */
function detectLayer(path: string): LayerId {
  const lower = path.toLowerCase();
  if (/(controller|routes?|api|endpoint|views?)/.test(lower)) return 'controller';
  if (/(service|services?|usecase|business)/.test(lower)) return 'service';
  if (/(repo|repository|repositories?|dao|database|db|store)/.test(lower)) return 'repository';
  if (/(model|models?|entity|entities?|schema|dto)/.test(lower)) return 'model';
  return 'shared';
}

/* Helper to detect language by extension */
function detectLang(path: string): string {
  if (/\.tsx?$/i.test(path)) return 'TypeScript';
  if (/\.jsx?$/i.test(path)) return 'JavaScript';
  if (/\.py$/i.test(path)) return 'Python';
  if (/\.java$/i.test(path)) return 'Java';
  if (/\.go$/i.test(path)) return 'Go';
  if (/\.rb$/i.test(path)) return 'Ruby';
  return 'TypeScript';
}

/* Helper to convert backend AnalysisResult into frontend ResultViewModel */
export function convertBackendResultToViewModel(raw: BackendAnalysisResult): ResultViewModel {
  const pathToId: Record<string, string> = {};
  const rawFiles = raw.files || [];

  const layerBuckets: Record<LayerId, typeof rawFiles> = {
    controller: [],
    service: [],
    repository: [],
    model: [],
    shared: [],
  };

  rawFiles.forEach((f, idx) => {
    const id = `f_${idx}_` + f.path.replace(/[^a-zA-Z0-9]/g, '_').slice(-20);
    pathToId[f.path] = id;
    const layer = detectLayer(f.path);
    layerBuckets[layer].push(f);
  });

  const layerX: Record<LayerId, number> = {
    controller: 10,
    service: 225,
    repository: 440,
    model: 655,
    shared: 870,
  };

  const allFiles: FileNode[] = [];
  const mapFiles: FileNode[] = [];

  LAYERS.forEach(layer => {
    const bucket = layerBuckets[layer.id];
    // Sort bucket by complexity and LOC
    bucket.sort((a, b) => (b.loc + (b.cognitive || 0) * 5) - (a.loc + (a.cognitive || 0) * 5));
    const x = layerX[layer.id];
    bucket.forEach((f, idx) => {
      const id = pathToId[f.path];
      const node: FileNode = {
        id,
        path: f.path,
        layer: layer.id,
        lang: detectLang(f.path),
        loc: f.loc,
        cyc: f.cyclomatic,
        cog: f.cognitive,
        nest: f.max_nesting,
        x,
        y: 40 + idx * 85,
      };
      allFiles.push(node);
      if (idx < 8) {
        mapFiles.push(node);
      }
    });
  });

  const files = mapFiles.length > 0 ? mapFiles : allFiles;
  const byId: Record<string, FileNode> = Object.fromEntries(allFiles.map(f => [f.id, f]));

  const rawEdges = raw.graph?.edges || [];
  const edges: Edge[] = [];
  rawEdges.forEach(e => {
    const fromId = pathToId[e.from];
    const toId = pathToId[e.to];
    if (fromId && toId && fromId !== toId) {
      edges.push([fromId, toId]);
    }
  });

  const rawCycles = raw.cycles || [];
  const cycles: Cycle[] = rawCycles.map(c => {
    const nodeIds = c.map(p => pathToId[p] || p);
    const names = c.map(p => p.split('/').pop() || p).join(', ');
    return {
      nodes: nodeIds,
      why: `Circular dependency detected between ${names}. This prevents isolated testing and increases coupling.`,
      fix: 'Extract shared interfaces or split concerns into a separate module.',
    };
  });

  const rawViolations = raw.architecture?.violations || [];
  const violations: Violation[] = rawViolations.map(v => {
    const fromId = pathToId[v.from] || v.from;
    const toId = pathToId[v.to] || v.to;
    const fromName = v.from.split('/').pop() || v.from;
    const toName = v.to.split('/').pop() || v.to;
    const title = v.rule
      ? v.rule
          .split('-')
          .map(w => w.charAt(0).toUpperCase() + w.slice(1))
          .join(' ')
      : 'Boundary violation';

    return {
      from: fromId,
      to: toId,
      rule: v.rule,
      title,
      why: `${fromName} directly references ${toName}, breaking expected architectural boundary constraints.`,
      fix: 'Reroute communication through intermediate abstraction layers.',
    };
  });

  const archVal = Math.round(raw.scores?.architecture_dna ?? 75);
  const codeVal = Math.round(raw.scores?.code_dna ?? 80);
  const qualVal = Math.round(raw.scores?.quality_dna ?? 70);

  const scores: Record<ScoreKey, Score> = {
    architecture: {
      value: archVal,
      name: 'Architecture DNA',
      text: `Pattern: ${raw.architecture?.pattern || 'Layered'}. ${cycles.length} cycles and ${violations.length} layer breaks detected.`,
    },
    code: {
      value: codeVal,
      name: 'Code DNA',
      text: `${raw.files?.length || 0} source files evaluated for complexity and size distribution.`,
    },
    quality: {
      value: qualVal,
      name: 'Quality DNA',
      text: `Evaluated for maximum nesting depth and cyclomatic/cognitive hot spots.`,
    },
  };

  const languages: Record<string, number> = {};
  if (raw.languages && raw.languages.length > 0) {
    raw.languages.forEach(l => {
      languages[l.name] = l.loc;
    });
  } else {
    files.forEach(f => {
      languages[f.lang] = (languages[f.lang] || 0) + f.loc;
    });
  }

  const frameworks =
    raw.frameworks?.map(f => (typeof f === 'string' ? f : f.name)) || ['Spring Boot', 'React'];

  const evidenceList =
    raw.architecture?.evidence && raw.architecture.evidence.length > 0
      ? raw.architecture.evidence
      : [
          `Detected architectural structure: ${raw.architecture?.pattern || 'Layered'}`,
          `${files.length} analyzed source files across architectural layers`,
          `${violations.length} architectural boundary violations found`,
        ];

  const violKeySet = new Set(violations.map(v => v.from + '>' + v.to));
  const cycleKeySet = new Set<string>();
  cycles.forEach(c =>
    c.nodes.forEach((n, i) => cycleKeySet.add(n + '>' + c.nodes[(i + 1) % c.nodes.length])),
  );
  const inCycleSet = new Set(cycles.flatMap(c => c.nodes));
  const inViolSet = new Set(violations.flatMap(v => [v.from, v.to]));

  const totalLoc = raw.repo_meta?.total_loc || files.reduce((acc, f) => acc + f.loc, 0);

  return {
    files,
    byId,
    edges,
    cycles,
    violations,
    scores,
    languages,
    frameworks,
    pattern: raw.architecture?.pattern || 'Layered',
    evidence: evidenceList,
    rawResult: raw,
    totals: { loc: totalLoc, files: files.length },
    violKey: violKeySet,
    cycleKey: cycleKeySet,
    inCycle: inCycleSet,
    inViol: inViolSet,
  };
}

export function getDemoResultViewModel(rawResult?: any): ResultViewModel {
  const langs: Record<string, number> = {};
  FILES.forEach(f => {
    langs[f.lang] = (langs[f.lang] || 0) + f.loc;
  });

  return {
    files: FILES,
    byId: BY_ID,
    edges: EDGES,
    cycles: CYCLES,
    violations: VIOLATIONS,
    scores: SCORES,
    languages: langs,
    frameworks: ['Express', 'Jest', 'npm'],
    pattern: 'Layered',
    evidence: evidence(),
    rawResult: rawResult || null,
    totals: totals(),
    violKey,
    cycleKey,
    inCycle,
    inViol,
  };
}
