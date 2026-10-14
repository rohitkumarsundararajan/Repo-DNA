import { useEffect, useRef } from 'react';
import type { HelixMode } from '../types';

interface HelixProps {
  mode?: HelixMode;
  lit?: number;
  total?: number;
  tall?: boolean;
}

const COLORS = { ok: ['#3F3DE6', '#E5307A'], fail: ['#8D91AE', '#D0708C'] };
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** The one animated thing: a double helix whose rungs light up as the analysis progresses. */
export default function Helix({ mode = 'idle', lit = 0, total = 26, tall = false }: HelixProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef({ mode, lit, total });
  stateRef.current = { mode, lit, total };

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d')!;
    const still = reduceMotion();
    let w = 0;
    let H = 0;
    let raf = 0;

    const size = () => {
      const r = canvas.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = r.width;
      H = r.height;
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    size();
    window.addEventListener('resize', size);

    const draw = (t: number) => {
      if (!w || !H) return;
      const s = stateRef.current;
      const N = s.total;
      const pad = 22;
      const amp = Math.min(w * 0.3, 96);
      const cx = w / 2;
      const [ca, cb] = s.mode === 'fail' ? COLORS.fail : COLORS.ok;
      const phase = still ? 0.6 : t * 0.0007;
      const k = 0.021;
      const step = 3;
      ctx.clearRect(0, 0, w, H);
      ctx.lineCap = 'round';

      const at = (y: number) => {
        const p = phase + y * k;
        return { s: Math.sin(p), z: Math.cos(p) };
      };
      const strands = (front: boolean) => {
        for (const which of [1, 2]) {
          ctx.strokeStyle = which === 1 ? ca : cb;
          for (let y = pad; y < H - pad; y += step) {
            const a = at(y);
            const b = at(y + step);
            const d = (which === 1 ? 1 : -1) * (a.z + b.z) / 2;
            if (d >= 0 !== front) continue;
            const sg = which === 1 ? 1 : -1;
            ctx.globalAlpha = 0.3 + (0.7 * (d + 1)) / 2;
            ctx.lineWidth = 2 + (2.4 * (d + 1)) / 2;
            ctx.beginPath();
            ctx.moveTo(cx + sg * amp * a.s, y);
            ctx.lineTo(cx + sg * amp * b.s, y + step);
            ctx.stroke();
          }
        }
        ctx.globalAlpha = 1;
      };

      strands(false);

      for (let i = 0; i < N; i++) {
        const y = pad + (i * (H - 2 * pad)) / (N - 1);
        const p = at(y);
        const x1 = cx + amp * p.s;
        const x2 = cx - amp * p.s;
        const isLit = s.mode === 'idle' || s.mode === 'done' || i < s.lit;
        const active = s.mode === 'work' && i === s.lit - 1;
        ctx.save();
        ctx.globalAlpha = s.mode === 'idle' ? 0.55 : 1;
        if (isLit) {
          const g = ctx.createLinearGradient(x1, y, x2, y);
          g.addColorStop(0, ca);
          g.addColorStop(1, cb);
          ctx.strokeStyle = g;
        } else ctx.strokeStyle = '#CDD1E4';
        if (active) {
          ctx.shadowColor = cb;
          ctx.shadowBlur = 14 + 6 * Math.sin(t / 160);
        }
        ctx.lineWidth = active ? 4 : 2.2;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.fillStyle = isLit ? ca : '#CDD1E4';
        ctx.beginPath();
        ctx.arc(x1, y, 3.8, 0, 7);
        ctx.fill();
        ctx.fillStyle = isLit ? cb : '#CDD1E4';
        ctx.beginPath();
        ctx.arc(x2, y, 3.8, 0, 7);
        ctx.fill();
        ctx.restore();
      }

      strands(true);
    };

    const tick = (t: number) => {
      if (!w) size();
      draw(t);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', size);
    };
  }, []);

  return (
    <div className={'helix-box' + (tall ? ' tall' : '')} aria-hidden="true">
      <canvas className="helix" ref={canvasRef} />
    </div>
  );
}
