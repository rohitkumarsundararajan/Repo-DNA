import type { Cycle, FileNode, Edge, Layer, PastJob, Score, ScoreKey, Stage, LogEntry, LogWho, Violation } from '../types';

/* Demo data: what the real API would return for a small shop API.
   When the backend is connected, these constants are replaced by API responses. */

export const LAYERS: Layer[] = [
  { id: 'controller', name: 'Controllers' },
  { id: 'service', name: 'Services' },
  { id: 'repository', name: 'Repositories' },
  { id: 'model', name: 'Models' },
  { id: 'shared', name: 'Shared' },
];

export const FILES: FileNode[] = [
  { id: 'ordersCtrl',   path: 'src/routes/orders.controller.ts',   layer: 'controller', lang: 'TypeScript', loc: 230, cyc: 16, cog: 22, nest: 4, x: 10,  y: 70  },
  { id: 'usersCtrl',    path: 'src/routes/users.controller.ts',    layer: 'controller', lang: 'TypeScript', loc: 110, cyc: 7,  cog: 8,  nest: 3, x: 10,  y: 355 },
  { id: 'productsCtrl', path: 'src/routes/products.controller.ts', layer: 'controller', lang: 'TypeScript', loc: 120, cyc: 8,  cog: 9,  nest: 3, x: 10,  y: 440 },
  { id: 'orderSvc',     path: 'src/services/order.service.ts',     layer: 'service',    lang: 'TypeScript', loc: 412, cyc: 28, cog: 41, nest: 6, x: 225, y: 40  },
  { id: 'pricingSvc',   path: 'src/services/pricing.service.ts',   layer: 'service',    lang: 'TypeScript', loc: 268, cyc: 19, cog: 27, nest: 5, x: 225, y: 150 },
  { id: 'inventorySvc', path: 'src/services/inventory.service.ts', layer: 'service',    lang: 'TypeScript', loc: 190, cyc: 14, cog: 18, nest: 4, x: 225, y: 260 },
  { id: 'userSvc',      path: 'src/services/user.service.ts',      layer: 'service',    lang: 'TypeScript', loc: 140, cyc: 9,  cog: 10, nest: 3, x: 225, y: 370 },
  { id: 'orderRepo',    path: 'src/repos/order.repo.ts',           layer: 'repository', lang: 'TypeScript', loc: 175, cyc: 11, cog: 13, nest: 3, x: 440, y: 70  },
  { id: 'userRepo',     path: 'src/repos/user.repo.ts',            layer: 'repository', lang: 'TypeScript', loc: 80,  cyc: 5,  cog: 4,  nest: 2, x: 440, y: 250 },
  { id: 'productRepo',  path: 'src/repos/product.repo.ts',         layer: 'repository', lang: 'TypeScript', loc: 98,  cyc: 6,  cog: 6,  nest: 2, x: 440, y: 440 },
  { id: 'orderModel',   path: 'src/models/order.ts',               layer: 'model',      lang: 'TypeScript', loc: 60,  cyc: 2,  cog: 1,  nest: 1, x: 655, y: 70  },
  { id: 'userModel',    path: 'src/models/user.ts',                layer: 'model',      lang: 'TypeScript', loc: 45,  cyc: 1,  cog: 0,  nest: 1, x: 655, y: 170 },
  { id: 'db',           path: 'src/config/db.js',                  layer: 'shared',     lang: 'JavaScript', loc: 40,  cyc: 1,  cog: 0,  nest: 1, x: 870, y: 250 },
  { id: 'format',       path: 'src/utils/format.js',               layer: 'shared',     lang: 'JavaScript', loc: 70,  cyc: 4,  cog: 3,  nest: 2, x: 870, y: 380 },
];

export const EDGES: Edge[] = [
  ['ordersCtrl', 'orderSvc'], ['usersCtrl', 'userSvc'], ['productsCtrl', 'productRepo'],
  ['orderSvc', 'pricingSvc'], ['pricingSvc', 'inventorySvc'], ['inventorySvc', 'orderSvc'],
  ['orderSvc', 'orderRepo'], ['orderRepo', 'orderSvc'],
  ['userSvc', 'userRepo'], ['orderRepo', 'orderModel'], ['userRepo', 'userModel'],
  ['userRepo', 'db'], ['productRepo', 'db'], ['userSvc', 'format'], ['productRepo', 'format'],
];

export const CYCLES: Cycle[] = [
  {
    nodes: ['orderSvc', 'pricingSvc', 'inventorySvc'],
    why: 'Pricing needs stock levels, stock needs order totals, and orders need pricing. Changing any one of them can break the other two.',
    fix: 'Move the shared price and stock rules into a small module that all three import.',
  },
  {
    nodes: ['orderSvc', 'orderRepo'],
    why: 'The order service and the order repository import each other, so neither can be tested or reused alone.',
    fix: 'Let the repository return plain data and keep the business rules in the service.',
  },
];

export const VIOLATIONS: Violation[] = [
  {
    from: 'productsCtrl', to: 'productRepo', rule: 'skips-layer', title: 'Skips a layer',
    why: 'The products controller reads the repository directly, so any business rule that belongs in a service is bypassed.',
    fix: 'Add a products service and call that from the controller.',
  },
  {
    from: 'orderRepo', to: 'orderSvc', rule: 'points-upward', title: 'Points upward',
    why: 'A repository should never import the layer above it. This is also what closes the loop in the second cycle.',
    fix: 'Remove the import and pass what the repository needs in as an argument.',
  },
];

export const SCORES: Record<ScoreKey, Score> = {
  architecture: { value: 72, name: 'Architecture DNA', text: 'The layers are easy to see: controllers call services, services call repositories. Two loops and two layer breaks pull the score down.' },
  code:         { value: 81, name: 'Code DNA',         text: 'Most files are short and simple to follow. Three files hold most of the complexity.' },
  quality:      { value: 64, name: 'Quality DNA',      text: 'order.service.ts is long and nests six levels deep, and two services depend on each other.' },
};

export const PAST_JOBS: PastJob[] = [
  { name: 'demo-org/shopwise-api',  when: 'Today, 09:12',     status: 'DONE' },
  { name: 'acme/legacy-monolith',   when: 'Yesterday, 16:40', status: 'FAILED', code: 'worker_timeout' },
  { name: 'northwind/billing-core', when: '3 days ago',       status: 'DONE' },
];

/* Pipeline stages: same order as the real worker */
export const STAGES: Stage[] = [
  { title: 'Waiting in line',                     text: 'The job sits in a Redis list until a worker is free.', ms: 1500 },
  { title: 'Copying the repo',                    text: 'A shallow clone inside a sandbox with 1 CPU, 1 GB of memory and a 120 second limit.', ms: 1700 },
  { title: 'Spotting languages and frameworks',   text: 'Read-only. Nothing from the repo is ever run.', ms: 1200 },
  { title: 'Reading every source file',           text: 'Each file is parsed into functions, classes and imports.', ms: 1600 },
  { title: 'Measuring complexity',                text: 'Cyclomatic, cognitive and nesting depth, file by file.', ms: 1800 },
  { title: 'Mapping who imports whom',            text: 'Every import becomes a line between two files.', ms: 1400 },
  { title: 'Looking for cycles and layer breaks', text: 'Files that depend on each other in a loop, and layers that are skipped or reversed.', ms: 1600 },
  { title: 'Scoring the three strands',           text: 'Architecture, Code and Quality, each out of 100.', ms: 1500 },
];

/* What the "Behind the scenes" panel says when each stage starts */
export const STAGE_LOGS: LogEntry[][] = [
  [['api', 'Called <code>POST /jobs</code>. The job is saved as Queued and you get its id straight back.'],
   ['redis', 'Pushed the job onto the list <code>repodna:jobs</code>.']],
  [['worker', 'A worker took the job off the list.'],
   ['worker', 'Called <code>POST /internal/jobs/{id}/status</code> with Running.'],
   ['worker', 'Cloning the repo in a sandbox.']],
  [['worker', 'Clone finished. 14 source files found.'],
   ['worker', 'Found TypeScript and JavaScript, using Express and Jest.']],
  [['worker', 'Parsing all 14 files in parallel.']],
  [['worker', 'Measuring complexity. 3 files are above the 15 cyclomatic warning line.']],
  [['score', 'Built the graph: 14 files and 15 imports.']],
  [['score', 'Found 2 cycles and 2 layer breaks. Layout looks like a Layered design.']],
  [['score', 'Scores are in: Architecture 72, Code 81, Quality 64.']],
];

export const WHO_NAME: Record<LogWho, string> = { api: 'API', redis: 'Queue', worker: 'Worker', score: 'Scorer' };
