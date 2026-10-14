import { useMemo, useState, type KeyboardEvent } from 'react';
import { CYCLES, EDGES, FILES, LAYERS, VIOLATIONS } from '../../data/demo';
import { BY_ID, cycleKey, fname, inCycle, inViol, layerIdx, violKey } from '../../lib/utils';
import type { ResultViewModel } from '../../lib/api';
import type { FileNode } from '../../types';

const NW = 170;
const NH = 50;

function edgePath(
  a: string,
  b: string,
  byId: Record<string, FileNode>,
  edges: [string, string][],
): string {
  const s = byId[a];
  const t = byId[b];
  if (!s || !t) return '';

  const cs = layerIdx(s.layer);
  const ct = layerIdx(t.layer);
  const mutual = edges.some(([x, y]) => x === b && y === a);
  if (cs < ct) {
    const dy = mutual ? -9 : 0;
    const x1 = s.x + NW,
      y1 = s.y + NH / 2 + dy,
      x2 = t.x,
      y2 = t.y + NH / 2 + dy;
    const d = Math.max(18, (x2 - x1) / 2);
    return `M${x1},${y1} C${x1 + d},${y1} ${x2 - d},${y2} ${x2},${y2}`;
  }
  if (cs > ct) {
    const dy = mutual ? 9 : 0;
    const x1 = s.x,
      y1 = s.y + NH / 2 + dy,
      x2 = t.x + NW,
      y2 = t.y + NH / 2 + dy;
    const d = Math.max(18, (x1 - x2) / 2);
    return `M${x1},${y1} C${x1 - d},${y1} ${x2 + d},${y2} ${x2},${y2}`;
  }
  if (t.y > s.y) {
    const x = s.x + NW / 2;
    return `M${x},${s.y + NH} L${x},${t.y}`;
  }
  const x1 = s.x,
    y1 = s.y + NH / 2,
    x2 = t.x,
    y2 = t.y + NH / 2 + 12;
  return `M${x1},${y1} C${x1 - 46},${y1} ${x2 - 46},${y2} ${x2},${y2}`;
}

const stripe = (f: FileNode) => (f.cog >= 20 ? 's-hot' : f.cog >= 10 ? 's-warm' : 's-cool');

interface Props {
  selected: string;
  onSelect: (id: string) => void;
  data?: ResultViewModel;
}

export default function ArchitecturePanel({ selected, onSelect, data }: Props) {
  const [showCycles, setShowCycles] = useState(true);
  const [showViol, setShowViol] = useState(true);
  const [hover, setHover] = useState<string | null>(null);

  const files = data ? data.files : FILES;
  const edges = data ? data.edges : EDGES;
  const cycles = data ? data.cycles : CYCLES;
  const violations = data ? data.violations : VIOLATIONS;
  const byId = data ? data.byId : BY_ID;
  const cycleKeySet = data ? data.cycleKey : cycleKey;
  const violKeySet = data ? data.violKey : violKey;
  const inCycleSet = data ? data.inCycle : inCycle;
  const inViolSet = data ? data.inViol : inViol;

  const currentSelected = byId[selected] ? selected : files[0]?.id || selected;

  const near = useMemo(() => {
    if (!hover) return null;
    const s = new Set([hover]);
    edges.forEach(([a, b]) => {
      if (a === hover) s.add(b);
      if (b === hover) s.add(a);
    });
    return s;
  }, [hover, edges]);

  const mapClass = ['show-cycles', 'show-viol'].filter((_, i) => (i === 0 ? showCycles : showViol)).join(' ');

  const maxFilesInCol = LAYERS.reduce(
    (max, l) => Math.max(max, files.filter(f => f.layer === l.id).length),
    1,
  );
  const svgHeight = Math.max(520, 50 + maxFilesInCol * 88);

  return (
    <>
      <div className="toolbar">
        <label>
          <input type="checkbox" checked={showCycles} onChange={e => setShowCycles(e.target.checked)} />
          Highlight cycles
        </label>
        <label>
          <input type="checkbox" checked={showViol} onChange={e => setShowViol(e.target.checked)} />
          Highlight layer breaks
        </label>
        <div className="key" aria-hidden="true">
          <span><i className="c" />In a cycle</span>
          <span><i className="v" />Breaks a layer rule</span>
          <span><b className="s-cool" style={{ background: 'var(--teal)' }} />Simple</span>
          <span><b style={{ background: 'var(--amber)' }} />Moderate</span>
          <span><b style={{ background: 'var(--b)' }} />Complex</span>
        </div>
      </div>

      <div className="arch">
        <div>
          <div className="diagram">
            <svg
              viewBox={`0 0 1050 ${svgHeight}`}
              className={mapClass}
              id="map"
              role="group"
              aria-label={`Dependency diagram of ${files.length} files. Use Tab to move between files.`}
            >
              <defs>
                {[['ar', '#A3A8C5'], ['ar-b', '#E5307A'], ['ar-y', '#E09A1A']].map(([id, c]) => (
                  <marker key={id} id={id} viewBox="0 0 10 10" refX={9} refY={5} markerWidth={9} markerHeight={9} markerUnits="userSpaceOnUse" orient="auto">
                    <path d="M0,0 L10,5 L0,10 z" fill={c} />
                  </marker>
                ))}
              </defs>

              {LAYERS.map((l, i) => {
                const x = 10 + i * 215;
                return (
                  <g key={l.id}>
                    <rect className="band" x={x - 10} y={0} width={NW + 20} height={svgHeight} rx={14} />
                    <text className="col-title" x={x} y={24}>{l.name}</text>
                  </g>
                );
              })}

              <g>
                {edges.map(([a, b]) => {
                  const k = a + '>' + b;
                  const cls = ['edge'];
                  if (cycleKeySet.has(k)) cls.push('cycle');
                  if (violKeySet.has(k)) cls.push('viol');
                  if (hover && a !== hover && b !== hover) cls.push('dim');
                  const fromNode = byId[a];
                  const toNode = byId[b];
                  return (
                    <path
                      key={k}
                      className={cls.join(' ')}
                      d={edgePath(a, b, byId, edges)}
                      data-from={a}
                      data-to={b}
                    >
                      <title>{fromNode && toNode ? `${fname(fromNode)} imports ${fname(toNode)}` : ''}</title>
                    </path>
                  );
                })}
              </g>

              <g>
                {files.map(f => {
                  const cls = ['node'];
                  if (inCycleSet.has(f.id)) cls.push('incycle');
                  if (inViolSet.has(f.id)) cls.push('inviol');
                  if (near && !near.has(f.id)) cls.push('dim');
                  if (currentSelected === f.id) cls.push('sel');
                  const onKey = (e: KeyboardEvent) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(f.id);
                    }
                  };
                  return (
                    <g
                      key={f.id}
                      className={cls.join(' ')}
                      data-id={f.id}
                      tabIndex={0}
                      role="button"
                      aria-label={`${fname(f)}, ${f.loc} lines, cognitive complexity ${f.cog}`}
                      onClick={() => onSelect(f.id)}
                      onKeyDown={onKey}
                      onMouseEnter={() => setHover(f.id)}
                      onMouseLeave={() => setHover(null)}
                      onFocus={() => setHover(f.id)}
                      onBlur={() => setHover(null)}
                    >
                      <rect className="halo" x={f.x - 4} y={f.y - 4} width={NW + 8} height={NH + 8} rx={12} />
                      <rect className="body" x={f.x} y={f.y} width={NW} height={NH} rx={9} />
                      <rect className={stripe(f)} x={f.x + 1} y={f.y + 8} width={5} height={NH - 16} rx={2.5} />
                      <text className="fname" x={f.x + 16} y={f.y + 21}>{fname(f)}</text>
                      <text className="fmeta" x={f.x + 16} y={f.y + 38}>{`${f.loc} lines`}</text>
                      <text className="fmeta" x={f.x + NW - 12} y={f.y + 38} textAnchor="end">{`${f.cog} cognitive`}</text>
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
          <p className="endpoint">
            Data from <code>GET /jobs/{'{id}'}/graph</code>, <code>/cycles</code> and <code>/violations</code>
          </p>
        </div>
        <Detail
          id={currentSelected}
          byId={byId}
          edges={edges}
          cycles={cycles}
          violations={violations}
        />
      </div>
    </>
  );
}

interface DetailProps {
  id: string;
  byId: Record<string, FileNode>;
  edges: [string, string][];
  cycles: typeof CYCLES;
  violations: typeof VIOLATIONS;
}

function Detail({ id, byId, edges, cycles, violations }: DetailProps) {
  const f = byId[id];
  if (!f) return null;

  const imports = edges.filter(([a]) => a === f.id).map(([, b]) => byId[b]).filter(Boolean);
  const importedBy = edges.filter(([, b]) => b === f.id).map(([a]) => byId[a]).filter(Boolean);
  const cycCount = cycles.filter(c => c.nodes.includes(f.id)).length;
  const viols = violations.filter(v => v.from === f.id || v.to === f.id);

  const Metric = ({ label, v, max, hot }: { label: string; v: number; max: number; hot: boolean }) => (
    <div className="m">
      <span>{label}</span>
      <span className="t"><i className={hot ? 'hot' : ''} style={{ width: `${Math.min(100, (v / max) * 100)}%` }} /></span>
      <b>{v}</b>
    </div>
  );
  const List = ({ items }: { items: FileNode[] }) =>
    items.length ? <ul>{items.map(x => <li key={x.id}>{fname(x)}</li>)}</ul> : <p className="empty">None</p>;

  return (
    <aside className="detail" aria-live="polite">
      <h3>{fname(f)}</h3>
      <div className="path">{f.path}</div>
      <div className="dl">
        <Metric label="Lines" v={f.loc} max={450} hot={false} />
        <Metric label="Cyclomatic" v={f.cyc} max={30} hot={f.cyc >= 15} />
        <Metric label="Cognitive" v={f.cog} max={45} hot={f.cog >= 20} />
        <Metric label="Nesting" v={f.nest} max={8} hot={f.nest >= 5} />
      </div>
      <h4>Imports</h4>
      <List items={imports} />
      <h4>Imported by</h4>
      <List items={importedBy} />
      {cycCount > 0 && (
        <div className="flagbox c">{`Part of ${cycCount} ${cycCount === 1 ? 'cycle' : 'cycles'}. See the Cycles and layer breaks tab.`}</div>
      )}
      {viols.map(v => (
        <div className="flagbox v" key={v.from + v.to}>
          {`${v.title}: ${fname(byId[v.from] || { path: v.from } as FileNode)} imports ${fname(byId[v.to] || { path: v.to } as FileNode)}.`}
        </div>
      ))}
      {!cycCount && viols.length === 0 && (
        <p className="empty" style={{ marginTop: 14 }}>No cycles or layer breaks involve this file.</p>
      )}
    </aside>
  );
}
