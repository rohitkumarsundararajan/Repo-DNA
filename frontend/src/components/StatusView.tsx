import { useEffect, useMemo, useRef } from 'react';
import Helix from './Helix';
import { STAGES, WHO_NAME } from '../data/demo';
import { stoppedState, useJobSimulation } from '../hooks/useJobSimulation';
import { useViewEnter } from '../hooks/useViewEnter';
import type { Job, JobStatus, PastJob, SimState } from '../types';

const PILL: Record<JobStatus, string> = { QUEUED: 'Queued', RUNNING: 'Running', DONE: 'Done', FAILED: 'Failed' };

interface StatusViewProps {
  job: Job;
  stopped?: PastJob;
  onOpenResults: (job: Job) => void;
  onTryAnother: () => void;
}

/** Live job: runs the fake timeline. */
function LiveStatus({ job, onOpenResults, onTryAnother }: Omit<StatusViewProps, 'stopped'>) {
  const sim = useJobSimulation(job, onOpenResults);
  return <StatusBody job={job} sim={sim} onOpenResults={onOpenResults} onTryAnother={onTryAnother} />;
}

export default function StatusView({ job, stopped, onOpenResults, onTryAnother }: StatusViewProps) {
  const frozen = useMemo(() => (stopped ? stoppedState(stopped) : null), [stopped]);
  return frozen ? (
    <StatusBody job={job} sim={frozen} onOpenResults={onOpenResults} onTryAnother={onTryAnother} />
  ) : (
    <LiveStatus job={job} onOpenResults={onOpenResults} onTryAnother={onTryAnother} />
  );
}

interface BodyProps {
  job: Job;
  sim: SimState;
  onOpenResults: (job: Job) => void;
  onTryAnother: () => void;
}

function StatusBody({ job, sim, onOpenResults, onTryAnother }: BodyProps) {
  const h1 = useViewEnter();
  const logRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const ul = logRef.current;
    if (ul) ul.scrollTop = ul.scrollHeight;
  }, [sim.logs.length]);

  const pollText =
    sim.polls === 0
      ? 'Checking in with the server every 2 seconds. You can close this page and the job keeps running.'
      : `Checked with the server ${sim.polls} time${sim.polls === 1 ? '' : 's'}. You can close this page and the job keeps running.`;

  return (
    <section className="view on" aria-labelledby="status-h">
      <div className="status-head">
        <div>
          <h1 id="status-h" tabIndex={-1} ref={h1}>Analysing <span>{job.name}</span></h1>
          <p className="meta-line">
            <span>Job <code>{job.id.slice(0, 8)}</code></span>
            <span>{sim.elapsed}</span>
            <span className="pill" data-s={sim.status}>{PILL[sim.status]}</span>
          </p>
        </div>
      </div>

      <div className="status-grid">
        <Helix tall mode={sim.helix.mode} lit={sim.helix.lit} />

        <div>
          <ol className="stages">
            {STAGES.map((s, i) => {
              const st = sim.stages[i];
              return (
                <li key={s.title} data-i={i} className={st === 'pending' ? undefined : st}>
                  <span className="st-ico" aria-hidden="true">{st === 'failed' ? '×' : String(i + 1)}</span>
                  <div>
                    <div className="st-title">{s.title}</div>
                    <div className="st-text">{s.text}</div>
                  </div>
                </li>
              );
            })}
          </ol>

          <p className="poll" hidden={sim.done || !!sim.fail}>{pollText}</p>

          <div className="fail-box" hidden={!sim.fail} role="alert">
            <h2>{sim.fail?.title}</h2>
            <p>{sim.fail?.text}</p>
            <p className="code-line">Reason saved on the job: <code>{sim.fail?.code}</code></p>
            <button className="btn primary" type="button" onClick={onTryAnother}>Try another repo</button>
          </div>

          <div className="done-box" hidden={!sim.done}>
            <p>The analysis is ready.</p>
            <button className="btn primary" type="button" onClick={() => onOpenResults({ ...job, took: sim.took })}>
              See the results
            </button>
          </div>

          <details className="scenes" open>
            <summary>Behind the scenes</summary>
            <p className="scenes-note">What the API, the queue, the worker and the scorer are doing for this job.</p>
            <ul className="log" aria-live="off" ref={logRef}>
              {sim.logs.map((l, i) => (
                <li key={i}>
                  <span className={'who-tag w-' + l.who}>{WHO_NAME[l.who]}</span>
                  <span dangerouslySetInnerHTML={{ __html: l.html }} />
                </li>
              ))}
            </ul>
          </details>
        </div>
      </div>
      <p className="sr" aria-live="polite">{sim.live}</p>
    </section>
  );
}
