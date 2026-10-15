export type LayerId = 'controller' | 'service' | 'repository' | 'model' | 'shared';

export interface Layer {
  id: LayerId;
  name: string;
}

export interface FileNode {
  id: string;
  path: string;
  layer: LayerId;
  lang: string;
  loc: number;
  cyc: number;
  cog: number;
  nest: number;
  x: number;
  y: number;
}

export type Edge = [from: string, to: string];

export interface Cycle {
  nodes: string[];
  why: string;
  fix: string;
}

export interface Violation {
  from: string;
  to: string;
  rule: string;
  title: string;
  why: string;
  fix: string;
}

export type ScoreKey = 'architecture' | 'code' | 'quality';

export interface Score {
  value: number;
  name: string;
  text: string;
}

export type JobStatus = 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED';

export interface PastJob {
  name: string;
  when: string;
  status: 'DONE' | 'FAILED';
  code?: string;
  id?: string;
}

export interface Job {
  id: string;
  name: string;
  url?: string;
  tooBig?: boolean;
  took?: number;
  isRealBackend?: boolean;
  rawResult?: any;
}

export interface Stage {
  title: string;
  text: string;
  ms: number;
}

export type LogWho = 'api' | 'redis' | 'worker' | 'score';
export type LogEntry = [who: LogWho, html: string];

export type StageState = 'pending' | 'active' | 'done' | 'failed';
export type HelixMode = 'idle' | 'work' | 'done' | 'fail';

export interface FailInfo {
  code: string;
  title: string;
  text: string;
}

export interface SimState {
  stages: StageState[];
  status: JobStatus;
  elapsed: string;
  polls: number;
  logs: { who: LogWho; html: string }[];
  helix: { mode: HelixMode; lit: number };
  fail: FailInfo | null;
  done: boolean;
  took?: number;
  live: string;
}

export type View =
  | { name: 'auth' }
  | { name: 'submit'; focusUrl?: boolean }
  | { name: 'status'; job: Job; stopped?: PastJob }
  | { name: 'results'; job: Job };
