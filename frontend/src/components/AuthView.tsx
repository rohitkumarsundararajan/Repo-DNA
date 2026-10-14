import { useState, type FormEvent } from 'react';
import Helix from './Helix';
import { useViewEnter } from '../hooks/useViewEnter';
import { login, register, setAuth } from '../lib/api';

export default function AuthView({ onSignIn }: { onSignIn: (email: string) => void }) {
  const h1 = useViewEnter();
  const [signUp, setSignUp] = useState(false);
  const [email, setEmail] = useState('demo@repodna.dev');
  const [pw, setPw] = useState('demo-password');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setErr('Please enter an email address.');
      return;
    }
    if (signUp && pw.length < 8) {
      setErr('Use at least 8 characters for password.');
      return;
    }

    setLoading(true);
    setErr('');

    try {
      if (signUp) {
        await register(cleanEmail, pw);
      } else {
        await login(cleanEmail, pw);
      }
      onSignIn(cleanEmail);
    } catch (e: any) {
      if (e.isBackendOffline) {
        // When backend service is offline, automatically activate local demo session with entered account
        setAuth('demo-token', cleanEmail);
        onSignIn(cleanEmail);
        return;
      }
      setErr(e.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const continueDemo = () => {
    onSignIn(email.trim() || 'demo@repodna.dev');
  };

  return (
    <section className="view on" aria-labelledby="auth-h">
      <div className="hero">
        <div className="hero-copy">
          <h1 id="auth-h" tabIndex={-1} ref={h1}>Sign in to analyse a repo</h1>
          <p className="lede">Your results stay private to your account. This is a demo, so the form is already filled in.</p>

          <div className="seg" role="tablist" aria-label="Account">
            <button
              type="button"
              role="tab"
              aria-selected={!signUp}
              onClick={() => {
                setSignUp(false);
                setErr('');
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={signUp}
              onClick={() => {
                setSignUp(true);
                setErr('');
              }}
            >
              Create account
            </button>
          </div>

          <form className="form" noValidate onSubmit={submit}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => {
                setEmail(e.target.value);
                setErr('');
              }}
              autoComplete="email"
            />
            <label htmlFor="pw">Password</label>
            <input
              id="pw"
              type="password"
              value={pw}
              onChange={e => {
                setPw(e.target.value);
                setErr('');
              }}
              autoComplete={signUp ? 'new-password' : 'current-password'}
            />
            <p className="hint" hidden={!signUp}>Use at least 8 characters.</p>

            {err && (
              <div>
                <p className="field-error" role="alert">{err}</p>
                <button
                  type="button"
                  className="link"
                  onClick={continueDemo}
                  style={{ fontSize: '0.88rem', marginTop: 4 }}
                >
                  Or continue in demo mode →
                </button>
              </div>
            )}

            <button className="btn primary" type="submit" disabled={loading}>
              {loading ? 'Connecting...' : signUp ? 'Create account' : 'Sign in'}
            </button>
          </form>
        </div>
        <Helix mode="idle" />
      </div>
    </section>
  );
}
