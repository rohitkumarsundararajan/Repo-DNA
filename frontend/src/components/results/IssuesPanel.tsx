import { CYCLES, VIOLATIONS } from '../../data/demo';
import { BY_ID, fname } from '../../lib/utils';
import type { ResultViewModel } from '../../lib/api';
import type { FileNode } from '../../types';

interface IssuesPanelProps {
  onShow: (id: string) => void;
  data?: ResultViewModel;
}

function Chain({
  nodes,
  close,
  byId,
}: {
  nodes: string[];
  close: boolean;
  byId: Record<string, FileNode>;
}) {
  const seq = close ? [...nodes, nodes[0]] : nodes;
  return (
    <div className="chain">
      {seq.map((n, i) => {
        const node = byId[n] || ({ id: n, path: n } as FileNode);
        return (
          <span key={i} style={{ display: 'contents' }}>
            {i > 0 && <span className="ar" aria-hidden="true">→</span>}
            <span className="f">{fname(node)}</span>
          </span>
        );
      })}
    </div>
  );
}

export default function IssuesPanel({ onShow, data }: IssuesPanelProps) {
  const cycles = data ? data.cycles : CYCLES;
  const violations = data ? data.violations : VIOLATIONS;
  const byId = data ? data.byId : BY_ID;

  return (
    <>
      <div className="issues">
        <div>
          <h2>{`Cycles (${cycles.length})`}</h2>
          <p className="sub" style={{ color: 'var(--ink-2)', margin: '6px 0 16px' }}>
            Files that depend on each other in a loop.
          </p>
          {cycles.length === 0 ? (
            <p className="empty" style={{ margin: '14px 0' }}>No dependency cycles detected in this repository.</p>
          ) : (
            cycles.map((c, i) => (
              <div className="issue" key={c.nodes.join('>') + i}>
                <h3>{`Cycle ${i + 1}: ${c.nodes.length} files`}</h3>
                <Chain nodes={c.nodes} close byId={byId} />
                <p>{c.why}</p>
                <p className="fix"><b>Try this:</b> {c.fix}</p>
                <button className="btn" type="button" onClick={() => onShow(c.nodes[0])}>
                  Show on the map
                </button>
              </div>
            ))
          )}
        </div>
        <div>
          <h2>{`Layer breaks (${violations.length})`}</h2>
          <p className="sub" style={{ color: 'var(--ink-2)', margin: '6px 0 16px' }}>
            Imports that go against the layered design.
          </p>
          {violations.length === 0 ? (
            <p className="empty" style={{ margin: '14px 0' }}>No layer boundary violations found.</p>
          ) : (
            violations.map((v, i) => (
              <div className="issue" key={v.from + v.to + i}>
                <h3>{v.title}</h3>
                <Chain nodes={[v.from, v.to]} close={false} byId={byId} />
                <p>{v.why}</p>
                <p className="fix"><b>Try this:</b> {v.fix}</p>
                <button className="btn" type="button" onClick={() => onShow(v.from)}>
                  Show on the map
                </button>
              </div>
            ))
          )}
        </div>
      </div>
      <p className="endpoint">
        Data from <code>GET /jobs/{'{id}'}/cycles</code> and <code>GET /jobs/{'{id}'}/violations</code>
      </p>
    </>
  );
}
