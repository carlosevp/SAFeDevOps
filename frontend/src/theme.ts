export type Theme = "light" | "dark";

const KEY = "safedevops_theme";

export function getTheme(): Theme {
  if (globalThis.window === undefined) return "light";
  const s = globalThis.localStorage.getItem(KEY);
  if (s === "dark" || s === "light") return s;
  if (globalThis.window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t === "dark" ? "dark" : "light";
  globalThis.localStorage.setItem(KEY, t);
}

export function initTheme(): void {
  applyTheme(getTheme());
}

export function toggleStoredTheme(current: Theme): Theme {
  const next: Theme = current === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
