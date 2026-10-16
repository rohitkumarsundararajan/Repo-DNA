import { useMemo, useRef, useState } from 'react';
import { buildResultJson } from '../../lib/utils';
import type { Job } from '../../types';

interface JsonPanelProps {
  job: Job;
  rawResult?: any;
}

export default function JsonPanel({ job, rawResult }: JsonPanelProps) {
  const text = useMemo(
    () => JSON.stringify(rawResult || job.rawResult || buildResultJson(job), null, 2),
    [job, rawResult],
  );
  const [label, setLabel] = useState('Copy JSON');
  const timer = useRef(0);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setLabel('Copied');
    } catch {
      setLabel('Select the text and copy');
    }
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setLabel('Copy JSON'), 1800);
  };

  return (
    <>
      <div className="json-bar">
        <p>
          This is the full result the worker sends back. The three views above are all built from it, so other tools
          can use the same data.
        </p>
        <button className="btn" type="button" onClick={copy}>{label}</button>
      </div>
      <pre className="json" tabIndex={0} aria-label="Result JSON">{text}</pre>
      <p className="endpoint">Data from <code>GET /jobs/{'{id}'}/result</code></p>
    </>
  );
}
