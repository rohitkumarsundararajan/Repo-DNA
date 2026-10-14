import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import Helix from './Helix';
import { PAST_JOBS } from '../data/demo';
import { useViewEnter } from '../hooks/useViewEnter';
import { getJobs, isLoggedIn, submitRepo, submitZip } from '../lib/api';
import { checkUrl, repoName, uuid } from '../lib/utils';
import type { Job, PastJob } from '../types';

interface SubmitViewProps {
  focusUrl?: boolean;
  onStart: (job: Job) => void;
  onOpenPast: (job: Job) => void;
  onShowStopped: (j: PastJob) => void;
}

const CHIPS = [
  { label: 'A small shop API', url: 'https://github.com/demo-org/shopwise-api' },
  { label: 'A repo that is too large', url: 'https://github.com/torvalds/linux' },
  { label: 'A broken link', url: 'github.com/just-a-name' },
];

function formatRelative(dateStr?: string): string {
  if (!dateStr) return 'Recently';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `Today, ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return 'Recently';
  }
}

export default function SubmitView({ focusUrl, onStart, onOpenPast, onShowStopped }: SubmitViewProps) {
  const h1 = useViewEnter(focusUrl);
  const urlRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState('');
  const [err, setErr] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [pastJobs, setPastJobs] = useState<PastJob[]>(PAST_JOBS);

  useEffect(() => {
    if (focusUrl) urlRef.current?.focus();
  }, [focusUrl]);

  useEffect(() => {
    let cancelled = false;
    getJobs()
      .then(jobs => {
        if (cancelled || !jobs || jobs.length === 0) return;
        const mapped: PastJob[] = jobs.map(j => ({
          id: j.job_id,
          name: j.repo_url ? repoName(j.repo_url) : `Uploaded ZIP (${j.job_id.slice(0, 8)})`,
          when: formatRelative(j.created_at),
          status: j.status === 'DONE' ? 'DONE' : 'FAILED',
          code: j.error || undefined,
        }));
        setPastJobs(mapped);
      })
      .catch(() => {
        // Keep demo jobs on network failure
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const v = url.trim();
    const problem = checkUrl(v);
    setErr(problem);
    if (problem) {
      urlRef.current?.focus();
      return;
    }

    const isTorvalds = /torvalds\/linux|huge/i.test(v);
    if (!isTorvalds) {
      setSubmitting(true);
      try {
        const res = await submitRepo(v);
        setSubmitting(false);
        onStart({ id: res.jobId, name: repoName(v), url: v, isRealBackend: true });
        return;
      } catch (e: any) {
        console.warn('Backend submission failed, falling back to simulation:', e);
        setSubmitting(false);
      }
    }
    onStart({ id: uuid(), name: repoName(v), url: v, tooBig: isTorvalds });
  };

  const fill = (v: string) => {
    setUrl(v);
    setErr('');
    urlRef.current?.focus();
  };

  const onZip = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;

    if (isLoggedIn()) {
      try {
        const res = await submitZip(f);
        onStart({
          id: res.jobId,
          name: f.name.replace(/\.zip$/i, '') + ' (ZIP)',
          url: '',
          tooBig: false,
          isRealBackend: true,
        });
        e.target.value = '';
        return;
      } catch (err: any) {
        console.warn('Backend ZIP submission failed, falling back to local demo:', err);
      }
    }

    onStart({ id: uuid(), name: f.name.replace(/\.zip$/i, '') + ' (ZIP)', url: '', tooBig: false });
    e.target.value = '';
  };

  return (
    <section className="view on" aria-labelledby="submit-h">
      <div className="hero">
        <div className="hero-copy">
          <h1 id="submit-h" tabIndex={-1} ref={h1}>Read your repo's DNA</h1>
          <p className="lede">
            Paste a GitHub or GitLab link. You get a map of how the files depend on each other, the loops and layer
            breaks hiding in it, and three scores out of 100.
          </p>

          <form className="submit" noValidate onSubmit={submit}>
            <label htmlFor="repo-url" className="sr">Repository link</label>
            <div className={'urlbar' + (err ? ' bad' : '')}>
              <input
                id="repo-url"
                ref={urlRef}
                type="url"
                inputMode="url"
                placeholder="https://github.com/owner/repo"
                autoComplete="off"
                spellCheck={false}
                aria-describedby="url-err"
                value={url}
                onChange={e => {
                  setUrl(e.target.value);
                  setErr('');
                }}
              />
              <button className="btn primary" type="submit" disabled={submitting}>
                {submitting ? 'Submitting...' : 'Analyse repo'}
              </button>
            </div>
            <p className="field-error" id="url-err" role="alert">{err}</p>

            <div className="try">
              <span>Try a demo:</span>
              {CHIPS.map(c => (
                <button key={c.url} type="button" className="chip" onClick={() => fill(c.url)}>{c.label}</button>
              ))}
            </div>

            <label className="zip" htmlFor="zip">
              <input id="zip" className="sr" type="file" accept=".zip" onChange={onZip} />
              <strong>No link? Upload a ZIP instead.</strong>
              <span>Choose a .zip of the project folder</span>
            </label>
          </form>
        </div>
        <Helix mode="idle" />
      </div>

      <div className="past">
        <h2>Your past analyses</h2>
        <ul className="jobs">
          {pastJobs.map((j, idx) => (
            <li key={j.id || j.name + idx}>
              <span className="repo">{j.name}</span>
              <span className="when">{j.when}</span>
              <span className="pill" data-s={j.status}>{j.status === 'DONE' ? 'Done' : 'Failed'}</span>
              <button
                className="btn"
                type="button"
                onClick={() =>
                  j.status === 'DONE'
                    ? onOpenPast({ name: j.name, id: j.id || uuid(), took: 11.8, isRealBackend: !!j.id })
                    : onShowStopped(j)
                }
              >
                {j.status === 'DONE' ? 'Open' : 'See why'}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
