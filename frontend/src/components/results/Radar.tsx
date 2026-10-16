import { SCORES } from '../../data/demo';
import type { Score, ScoreKey } from '../../types';

const W = 400, HH = 360, CX = 200, CY = 190, R = 120;

const AXES: { key: ScoreKey; label: string; ang: number; anchor: 'start' | 'middle' | 'end'; dx: number; dy: number }[] = [
  { key: 'architecture', label: 'Architecture', ang: -90, anchor: 'middle', dx: 0, dy: -18 },
  { key: 'code', label: 'Code', ang: 30, anchor: 'start', dx: 14, dy: 18 },
  { key: 'quality', label: 'Quality', ang: 150, anchor: 'end', dx: -14, dy: 18 },
];

const pt = (ang: number, r: number): [number, number] => [
  CX + r * Math.cos((ang * Math.PI) / 180),
  CY + r * Math.sin((ang * Math.PI) / 180),
];
const poly = (pts: [number, number][]) => pts.map(p => p.join(',')).join(' ');

interface RadarProps {
  k: number;
  scores?: Record<ScoreKey, Score>;
}

/** Radar chart of the three scores; `k` (0..1) is the grow-in animation progress. */
export default function Radar({ k, scores }: RadarProps) {
  const sMap = scores || SCORES;
  const pts = AXES.map(a => pt(a.ang, (R * (sMap[a.key]?.value ?? 0)) / 100 * k));
  return (
    <svg viewBox={`0 0 ${W} ${HH}`} aria-hidden="true">
      {[25, 50, 75, 100].map(r => (
        <polygon
          key={r}
          points={poly(AXES.map(a => pt(a.ang, (R * r) / 100)))}
          fill={r === 100 ? '#fff' : 'none'}
          stroke="#DCDFEE"
          strokeWidth={1.2}
        />
      ))}
      {AXES.map(a => {
        const [x, y] = pt(a.ang, R);
        return <line key={a.key} x1={CX} y1={CY} x2={x} y2={y} stroke="#DCDFEE" strokeWidth={1.2} />;
      })}
      {[50, 100].map(r => (
        <text key={r} x={CX + 6} y={CY - (R * r) / 100 + 12} fontSize={10.5} fill="#6E7292" fontFamily="Instrument Sans, sans-serif">
          {r}
        </text>
      ))}
      <polygon points={poly(pts)} fill="rgba(63,61,230,.16)" stroke="#3F3DE6" strokeWidth={2.6} strokeLinejoin="round" />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={5.5} fill="#E5307A" stroke="#fff" strokeWidth={2} />
      ))}
      {AXES.map(a => {
        const [x, y] = pt(a.ang, R);
        return (
          <text
            key={a.key}
            x={x + a.dx}
            y={y + a.dy}
            textAnchor={a.anchor}
            fontFamily="Bricolage Grotesque, sans-serif"
            fontWeight={700}
            fontSize={16}
            fill="#16182E"
          >
            {`${a.label} ${Math.round((sMap[a.key]?.value ?? 0) * k)}`}
          </text>
        );
      })}
    </svg>
  );
}
