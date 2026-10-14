import { useState } from 'react';
import Header from './components/Header';
import AuthView from './components/AuthView';
import SubmitView from './components/SubmitView';
import StatusView from './components/StatusView';
import ResultsView from './components/ResultsView';
import { getUser, logout } from './lib/api';
import { uuid } from './lib/utils';
import type { Job, PastJob, View } from './types';

export default function App() {
  const [user, setUser] = useState<string | null>(() => getUser());
  const [view, setView] = useState<View>(() => (getUser() ? { name: 'submit' } : { name: 'auth' }));

  const goSubmit = (focusUrl = false) => setView({ name: 'submit', focusUrl });

  const signIn = (email: string) => {
    setUser(email);
    goSubmit();
  };
  const signOut = () => {
    logout();
    setUser(null);
    setView({ name: 'auth' });
  };
  const startJob = (job: Job) => setView({ name: 'status', job });
  const showStopped = (j: PastJob) =>
    setView({ name: 'status', job: { id: j.id || uuid(), name: j.name, isRealBackend: !!j.id }, stopped: j });
  const openResults = (job: Job) => setView({ name: 'results', job });

  return (
    <>
      <Header user={user} onHome={() => goSubmit()} onNew={() => goSubmit()} onSignOut={signOut} />

      <main className="wrap">
        {view.name === 'auth' && <AuthView onSignIn={signIn} />}
        {view.name === 'submit' && (
          <SubmitView
            key={view.focusUrl ? 'focus' : 'plain'}
            focusUrl={view.focusUrl}
            onStart={startJob}
            onOpenPast={openResults}
            onShowStopped={showStopped}
          />
        )}
        {view.name === 'status' && (
          <StatusView
            key={view.job.id}
            job={view.job}
            stopped={view.stopped}
            onOpenResults={openResults}
            onTryAnother={() => goSubmit(true)}
          />
        )}
        {view.name === 'results' && <ResultsView key={view.job.id} job={view.job} onNew={() => goSubmit()} />}
      </main>

      <footer className="foot">
        <div className="wrap">
          RepoDNA — Analyzing repository architecture, complexity, and dependencies with live code metrics.
        </div>
      </footer>
    </>
  );
}
