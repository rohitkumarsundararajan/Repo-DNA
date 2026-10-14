import { useEffect, useState } from 'react';
import Radar from './Radar';
import { FILES, SCORES } from '../../data/demo';
import { evidence, fmt, fname, totals } from '../../lib/utils';
import type { ResultViewModel } from '../../lib/api';
import type { ScoreKey } from '../../types';

const LANG_COLORS: Record<string, string> = {
  TypeScript: 'var(--a)',
  JavaScript: 'var(--amber)',
  Python: '#3776AB',
  Java: '#E5307A',
  Go: '#00ADD8',
  Ruby: '#CC342D',
};

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

interface ScoresPanelProps {
  active: boolean;
  data?: ResultViewModel;
}

export default function ScoresPanel({ active, data }: ScoresPanelProps) {
  const [k, setK] = useState(0);
  const [grown, setGrown] = useState(false);

  /* Replay the radar + bar animation each time the tab is shown */
  useEffect(() => {
    if (!active) return;
    let raf = 0;
    let r1 = 0;
    let r2 = 0;
    let cancelled = false;
    const t0 = performance.now();
    const dur = reduceMotion() ? 1 : 900;
    const step = (now: number) => {
      if (cancelled) return;
      const p = Math.min(1, (now - t0) / dur);
      setK(1 - Math.pow(1 - p, 3));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    setK(0);
    setGrown(false);
    raf = requestAnimationFrame(step);
    r1 = requestAnimationFrame(() => {
      r2 = requestAnimationFrame(() => !cancelled && setGrown(true));
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      cancelAnimationFrame(r1);
      cancelAnimationFrame(r2);
    };
  }, [active]);

  const files = data ? data.files : FILES;
  const scores = data ? data.scores : SCORES;
  const t = data ? data.totals : totals();
  const evidenceList = data ? data.evidence : evidence();
  const pattern = data ? data.pattern : 'Layered';
  const frameworks = data ? data.frameworks : ['Express', 'Jest', 'npm'];

  const langs: Record<string, number> = data
    ? data.languages
    : (() => {
        const m: Record<string, number> = {};
        FILES.forEach(f => {
          m[f.lang] = (m[f.lang] || 0) + f.loc;
        });
        return m;
      })();

  const top = [...files].sort((a, b) => b.cog - a.cog || b.cyc - a.cyc).slice(0, 10);
  const max = Math.max(1, top[0]?.cog || 1);

  return (
    <>
      <div className="dash-top">
        <div
          className="radar"
          role="img"
          aria-label={`Radar chart. Architecture ${scores.architecture.value}, Code ${scores.code.value}, Quality ${scores.quality.value}.`}
        >
          <Radar k={k} scores={scores} />
        </div>
        <div className="scores">
          {(Object.keys(scores) as ScoreKey[]).map(key => {
            const s = scores[key];
            return (
              <div className="score" key={key}>
                <div className="num">{s.value}<small> /100</small></div>
                <div>
                  <h3>{s.name}</h3>
                  <div className="bar"><i style={{ width: grown ? `${s.value}%` : '0' }} /></div>
                </div>
                <p>{s.text}</p>
              </div>
            );
          })}
        </div>
      </div>
      <p className="endpoint">Data from <code>GET /jobs/{'{id}'}/dashboard</code></p>

      <div className="section">
        <h2>What is in the repo</h2>
        <div className="repo-grid">
          <div>
            <h3>Languages</h3>
            <div className="langbar" role="img" aria-label="Share of lines by language">
              {Object.entries(langs).map(([n, v]) => (
                <i
                  key={n}
                  style={{
                    width: `${(v / Math.max(1, t.loc)) * 100}%`,
                    background: LANG_COLORS[n] || 'var(--a)',
                  }}
                />
              ))}
            </div>
            <ul className="legend">
              {Object.entries(langs).map(([n, v]) => (
                <li key={n}>
                  <span className="sw" style={{ background: LANG_COLORS[n] || 'var(--a)' }} />
                  {n}
                  <span className="n">{`${Math.round((v / Math.max(1, t.loc)) * 100)}%, ${fmt(v)} lines`}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Frameworks and tools</h3>
            <div className="tags">
              {frameworks.map(x => (
                <span className="tag" key={x}>{x}</span>
              ))}
            </div>
          </div>
          <div>
            <h3>Architecture pattern</h3>
            <div className="pattern">{pattern}</div>
            <ul className="evidence">
              {evidenceList.map(e => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="section">
        <h2>Complexity hotspots</h2>
        <p className="sub">The ten files that are hardest to read, ranked by cognitive complexity. Start refactoring at the top.</p>
        <div className="hs" role="list">
          {top.map(f => {
            const hot = f.cyc >= 15;
            return (
              <div className="hs-row" role="listitem" key={f.id}>
                <span className="hs-name" title={f.path}>{fname(f)}</span>
                <span className="hs-track">
                  <i className={'hs-fill' + (hot ? ' hot' : '')} style={{ width: grown ? `${((f.cog / max) * 100).toFixed(1)}%` : '0' }} />
                </span>
                <span className="hs-val">
                  <b>{f.cog}</b>{` cognitive, ${f.cyc} cyclomatic `}
                  {hot ? <span className="flag">needs attention</span> : null}
                </span>
              </div>
            );
          })}
        </div>
        <p className="hs-note">Pink bars mark files with a cyclomatic score of 15 or more, which are hard to test.</p>
        <p className="endpoint">Data from <code>GET /jobs/{'{id}'}/dashboard</code></p>
      </div>
    </>
  );
}
