import { useEffect, useState, type KeyboardEvent } from 'react';
import ScoresPanel from './results/ScoresPanel';
import ArchitecturePanel from './results/ArchitecturePanel';
import IssuesPanel from './results/IssuesPanel';
import JsonPanel from './results/JsonPanel';
import { useViewEnter } from '../hooks/useViewEnter';
import {
  convertBackendResultToViewModel,
  getDemoResultViewModel,
  getResult,
  type ResultViewModel,
} from '../lib/api';
import { fmt } from '../lib/utils';
import type { Job } from '../types';

type TabId = 'dash' | 'arch' | 'issues' | 'json';

interface ResultsViewProps {
  job: Job;
  onNew: () => void;
}

export default function ResultsView({ job, onNew }: ResultsViewProps) {
  const h1 = useViewEnter();
  const [tab, setTab] = useState<TabId>('dash');
  const [resultData, setResultData] = useState<ResultViewModel>(() =>
    getDemoResultViewModel(job.rawResult),
  );
  const [selected, setSelected] = useState<string>(() => resultData.files[3]?.id || 'orderSvc');

  useEffect(() => {
    let cancelled = false;
    // Attempt to load from real backend
    getResult(job.id)
      .then(res => {
        if (cancelled || !res) return;
        const vm = convertBackendResultToViewModel(res);
        setResultData(vm);
        if (vm.files.length > 0) {
          setSelected(vm.files[0].id);
        }
      })
      .catch(() => {
        // Fall back to demo data if backend result is not available
      });

    return () => {
      cancelled = true;
    };
  }, [job.id]);

  const t = resultData.totals;
  const issuesCount = resultData.cycles.length + resultData.violations.length;

  const tabs: { id: TabId; label: React.ReactNode }[] = [
    { id: 'dash', label: 'Scores' },
    { id: 'arch', label: 'Architecture map' },
    {
      id: 'issues',
      label: (
        <>Cycles and layer breaks <span className="badge">{issuesCount}</span></>
      ),
    },
    { id: 'json', label: 'Raw result' },
  ];

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const i = tabs.findIndex(x => x.id === tab);
    const n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    setTab(n.id);
    requestAnimationFrame(() => document.getElementById('t-' + n.id)?.focus());
  };

  const showOnMap = (id: string) => {
    setSelected(id);
    setTab('arch');
    requestAnimationFrame(() => document.getElementById('t-arch')?.focus());
  };

  return (
    <section className="view on" aria-labelledby="res-h">
      <div className="res-head">
        <div>
          <h1 id="res-h" tabIndex={-1} ref={h1}>{job.name}</h1>
          <p className="meta-line">
            <span>{`Finished in ${(job.took || 11.8).toFixed(1)} s`}</span>
            <span>{`${t.files} files`}</span>
            <span>{`${fmt(t.loc)} lines`}</span>
            <span>Job <code>{job.id.slice(0, 8)}</code></span>
            <span className="pill" data-s="DONE">Done</span>
          </p>
        </div>
        <button className="btn" type="button" onClick={onNew}>Analyse another repo</button>
      </div>

      <div className="tabs" role="tablist" aria-label="Result views" onKeyDown={onKeyDown}>
        {tabs.map(x => (
          <button
            key={x.id}
            className="tab"
            role="tab"
            id={'t-' + x.id}
            aria-controls={'p-' + x.id}
            aria-selected={tab === x.id}
            tabIndex={tab === x.id ? 0 : -1}
            type="button"
            onClick={() => setTab(x.id)}
          >
            {x.label}
          </button>
        ))}
      </div>

      <div className={'panel' + (tab === 'dash' ? ' on' : '')} id="p-dash" role="tabpanel" aria-labelledby="t-dash">
        <ScoresPanel active={tab === 'dash'} data={resultData} />
      </div>
      <div className={'panel' + (tab === 'arch' ? ' on' : '')} id="p-arch" role="tabpanel" aria-labelledby="t-arch">
        <ArchitecturePanel selected={selected} onSelect={setSelected} data={resultData} />
      </div>
      <div className={'panel' + (tab === 'issues' ? ' on' : '')} id="p-issues" role="tabpanel" aria-labelledby="t-issues">
        <IssuesPanel onShow={showOnMap} data={resultData} />
      </div>
      <div className={'panel' + (tab === 'json' ? ' on' : '')} id="p-json" role="tabpanel" aria-labelledby="t-json">
        <JsonPanel job={job} rawResult={resultData.rawResult} />
      </div>
    </section>
  );
}
