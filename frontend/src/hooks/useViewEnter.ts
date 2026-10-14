import { useEffect, useRef } from 'react';

/** Scrolls to top and moves focus to the view's <h1> when the view appears (keeps the original a11y behaviour). */
export function useViewEnter<T extends HTMLElement = HTMLHeadingElement>(skipFocus = false) {
  const ref = useRef<T>(null);
  useEffect(() => {
    window.scrollTo(0, 0);
    if (!skipFocus) ref.current?.focus({ preventScroll: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return ref;
}
