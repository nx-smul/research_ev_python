import { useEffect, useState } from 'react';

const THEME_KEY = 'dhaka-evcs-theme';

export function useTheme(initialTheme = null) {
  const [theme, setTheme] = useState(() => initialTheme || (() => {
    const saved = window.localStorage.getItem(THEME_KEY);
    return ['auto', 'light', 'dark'].includes(saved) ? saved : 'auto';
  })());
  const [resolvedTheme, setResolvedTheme] = useState('light');

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const applyTheme = () => {
      const resolved = theme === 'auto' ? (media?.matches ? 'dark' : 'light') : theme;
      document.documentElement.dataset.theme = resolved;
      document.querySelector('meta[name="theme-color"]')?.setAttribute(
        'content',
        resolved === 'dark' ? '#0d111b' : '#f4f6fa',
      );
      setResolvedTheme(resolved);
    };
    applyTheme();
    window.localStorage.setItem(THEME_KEY, theme);
    if (theme !== 'auto' || !media) return undefined;
    media.addEventListener?.('change', applyTheme);
    return () => media.removeEventListener?.('change', applyTheme);
  }, [theme]);

  return { theme, setTheme, resolvedTheme };
}
