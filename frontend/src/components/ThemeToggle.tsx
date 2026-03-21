import { useState } from "react";
import { getTheme, toggleStoredTheme, type Theme } from "../theme";

export function ThemeToggle() {
  const [mode, setMode] = useState<Theme>(() => getTheme());

  return (
    <button
      type="button"
      className="btn btn-ghost btn-compact"
      aria-label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setMode(toggleStoredTheme(mode))}
    >
      {mode === "dark" ? "Light mode" : "Dark mode"}
    </button>
  );
}
