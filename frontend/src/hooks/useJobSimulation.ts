import { useEffect, useRef, useState } from 'react';
import { STAGES, STAGE_LOGS } from '../data/demo';
import { getJob } from '../lib/api';
import type { Job, PastJob, SimState, StageState } from '../types';

const initialState = (): SimState => ({
  stages: STAGES.map((): StageState => 'pending'),
  status: 'QUEUED',
  elapsed: '0.0 s',
  polls: 0,
  logs: [],
  helix: { mode: 'work', lit: 0 },
  fail: null,
  done: false,
  live: '',
});

/** Static "failed" state for a job that already failed in the past. */
export function stoppedState(j: PastJob): SimState {
  const code = j.code || 'worker_timeout';
  return {
    stages: STAGES.map((_, i): StageState => (i < 4 ? 'done' : i === 4 ? 'failed' : 'pending')),
    status: 'FAILED',
    elapsed: '10 min 0 s',
    polls: 0,
    logs: [
      { who: 'worker', html: 'Started measuring complexity, then stopped reporting back.' },
      { who: 'api', html: 'A cleanup task that runs every minute saw the job stuck in Running for over 10 minutes.' },
      { who: 'api', html: `Marked the job Failed with the reason <code>${code}</code>.` },
    ],
    helix: { mode: 'fail', lit: 12 },
    fail: {
      code,
      title: 'The analysis stopped',
      text:
        code === 'worker_timeout'
          ? 'The worker did not report back within 10 minutes, so the job was stopped. Try again, or upload a smaller part of the project.'
          : `The job stopped with reason: ${code}. Check repository requirements and try again.`,
    },
    done: false,
    live: 'The analysis stopped',
  };
}

const stageStates = (cur: number): StageState[] =>
  STAGES.map((_, n): StageState => (n < cur ? 'done' : n === cur ? 'active' : 'pending'));

/**
 * Handles job timeline:
 * If the job is submitted to the real backend, polls GET /jobs/{id} every 2 seconds.
 * If backend is offline or for demo jobs, uses the smooth simulated flow.
 */
export function useJobSimulation(job: Job, onDone: (job: Job) => void): SimState {
  const [sim, setSim] = useState<SimState>(initialState);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    let cancelled = false;
    let raf = 0;
    let openTimer = 0;
    let pollTimer = 0;
    let state = initialState();
    setSim(state);

    const push = (patch: Partial<SimState>) => {
      state = { ...state, ...patch };
      setSim(state);
    };

    const starts: number[] = [];
    let acc = 0;
    STAGES.forEach(s => {
      starts.push(acc);
      acc += s.ms;
    });
    const total = acc;
    const t0 = performance.now();
    let cur = -1;

    const enter = (i: number) => {
      push({
        stages: stageStates(i),
        status: i >= 1 ? 'RUNNING' : state.status,
        live: STAGES[i].title,
        logs: [...state.logs, ...(STAGE_LOGS[i] || []).map(([who, html]) => ({ who, html }))],
      });
    };

    const fail = (code: string, title: string, text: string) => {
      clearInterval(pollTimer);
      cancelAnimationFrame(raf);
      const stages = stageStates(cur >= 0 ? cur : 1);
      stages[cur >= 0 ? cur : 1] = 'failed';
      push({
        stages,
        status: 'FAILED',
        helix: { mode: 'fail', lit: state.helix.lit },
        logs: [
          ...state.logs,
          { who: 'worker', html: 'Worker process stopped reporting back.' },
          {
            who: 'worker',
            html: `Called <code>POST /internal/jobs/{id}/status</code> with Failed and reason <code>${code}</code>.`,
          },
          { who: 'api', html: 'Marked the job Failed and saved the reason.' },
        ],
        fail: { code, title, text },
        live: title,
      });
    };

    const finish = (tookSeconds?: number) => {
      clearInterval(pollTimer);
      cancelAnimationFrame(raf);
      const took = tookSeconds ?? (performance.now() - t0) / 1000;
      push({
        stages: STAGES.map((): StageState => 'done'),
        status: 'DONE',
        helix: { mode: 'done', lit: 26 },
        logs: [
          ...state.logs,
          { who: 'worker', html: 'Called <code>POST /internal/jobs/{id}/result</code>. The API answered 204.' },
          { who: 'api', html: 'Checked the result against the shared contract, saved it, and marked the job Done.' },
        ],
        done: true,
        took,
        live: 'The analysis is ready',
      });
      openTimer = window.setTimeout(() => {
        if (!cancelled) onDoneRef.current({ ...job, took });
      }, 2600);
    };

    // If real backend job, poll GET /jobs/{id}
    if (job.isRealBackend) {
      let stageIdx = 0;
      enter(0);

      const checkBackend = async () => {
        if (cancelled) return;
        try {
          const res = await getJob(job.id);
          push({ polls: state.polls + 1 });

          if (res.status === 'RUNNING' && stageIdx === 0) {
            stageIdx = 1;
            enter(1);
          } else if (res.status === 'RUNNING' && stageIdx < STAGES.length - 1) {
            stageIdx++;
            enter(stageIdx);
          }

          if (res.status === 'DONE') {
            const took = (performance.now() - t0) / 1000;
            finish(took);
            return;
          }

          if (res.status === 'FAILED') {
            fail(
              res.error || 'worker_failed',
              'The analysis failed',
              res.error || 'The worker encountered an error while analyzing the repository.',
            );
            return;
          }
        } catch (e: any) {
          // If polling fails or 404, fall back to smooth simulation
          console.warn('Backend polling error, continuing with simulation:', e);
        }
      };

      pollTimer = window.setInterval(checkBackend, 2000);
      checkBackend();

      const loopReal = (now: number) => {
        if (cancelled || state.done || state.fail) return;
        const el = now - t0;
        const elapsed = (el / 1000).toFixed(1) + ' s';
        const lit = Math.min(26, Math.floor((el / 12000) * 26));
        if (elapsed !== state.elapsed || lit !== state.helix.lit) {
          push({ elapsed, helix: { mode: 'work', lit } });
        }
        raf = requestAnimationFrame(loopReal);
      };
      raf = requestAnimationFrame(loopReal);

      return () => {
        cancelled = true;
        cancelAnimationFrame(raf);
        clearInterval(pollTimer);
        clearTimeout(openTimer);
      };
    }

    // Default simulation flow
    pollTimer = window.setInterval(() => {
      if (cancelled) return;
      push({ polls: state.polls + 1 });
    }, 2000);

    const loop = (now: number) => {
      if (cancelled) return;
      const el = now - t0;
      let idx = 0;
      for (let i = 0; i < starts.length; i++) if (el >= starts[i]) idx = i;
      const frac = Math.min(1, (el - starts[idx]) / STAGES[idx].ms);
      if (idx !== cur) {
        cur = idx;
        enter(idx);
      }
      const elapsed = (Math.min(el, total) / 1000).toFixed(1) + ' s';
      const lit = Math.floor(((idx + frac) / STAGES.length) * 26);
      if (elapsed !== state.elapsed || lit !== state.helix.lit) {
        push({ elapsed, helix: { mode: 'work', lit } });
      }

      if (job.tooBig && idx === 1 && frac > 0.6) {
        return fail(
          'repo_too_large',
          'This repo is too large to analyse',
          'The clone grew past the 1 GB limit, so the worker stopped. Try a smaller repo, or upload a ZIP of just the folder you care about.',
        );
      }
      if (el >= total) return finish();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      clearInterval(pollTimer);
      clearTimeout(openTimer);
    };
  }, [job]);

  return sim;
}
