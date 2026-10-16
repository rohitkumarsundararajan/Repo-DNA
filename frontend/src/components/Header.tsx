import type { MouseEvent } from 'react';

interface HeaderProps {
  user: string | null;
  onHome: () => void;
  onNew: () => void;
  onSignOut: () => void;
}

export default function Header({ user, onHome, onNew, onSignOut }: HeaderProps) {
  const brandClick = (e: MouseEvent) => {
    e.preventDefault();
    if (user) onHome();
  };
  return (
    <header className="top">
      <div className="wrap top-in">
        <a className="brand" href="#" onClick={brandClick} aria-label="RepoDNA home">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
            <path d="M6 2 C 20 8, 6 18, 20 24" fill="none" stroke="#3F3DE6" strokeWidth="2.6" strokeLinecap="round" />
            <path d="M20 2 C 6 8, 20 18, 6 24" fill="none" stroke="#E5307A" strokeWidth="2.6" strokeLinecap="round" />
            <path d="M9 7.5h8M7.5 13h11M9 18.5h8" stroke="#16182E" strokeWidth="1.6" strokeLinecap="round" opacity=".55" />
          </svg>
          <span>RepoDNA</span>
        </a>
        <nav className="nav" hidden={!user}>
          <button className="link" type="button" onClick={onNew}>New analysis</button>
          <span className="who">{user}</span>
          <button className="link" type="button" onClick={onSignOut}>Sign out</button>
        </nav>
      </div>
    </header>
  );
}
