import { useState } from "react";

const DEFAULT_TITLE = "SAFe DevOps self-assessment";
const DEFAULT_LOGO = "/logo-placeholder.svg";

function resolveLogoSrc(prop?: string): string | null {
  if (prop !== undefined) return prop.trim() || null;
  const raw = import.meta.env.VITE_APP_LOGO_URL;
  if (raw === "") return null;
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  return DEFAULT_LOGO;
}

type Props = {
  title?: string;
  /** Public URL (e.g. file in `public/`). Pass "" to hide via prop override. */
  logoUrl?: string;
  subtitle?: string;
  children?: React.ReactNode;
};

export function AppHeader({ title, logoUrl, subtitle, children }: Props) {
  const resolvedTitle = (title ?? import.meta.env.VITE_APP_TITLE?.trim()) || DEFAULT_TITLE;
  const src = resolveLogoSrc(logoUrl);
  const [logoBroken, setLogoBroken] = useState(false);

  return (
    <header className="app-header">
      <div className="app-header-brand">
        {src && !logoBroken ? (
          <img
            src={src}
            alt=""
            className="app-logo"
            width={160}
            height={36}
            decoding="async"
            onError={() => setLogoBroken(true)}
          />
        ) : (
          <span className="app-logo-fallback" aria-hidden>
            Assessment
          </span>
        )}
        <div className="app-header-titles">
          <h1 className="app-header-title">{resolvedTitle}</h1>
          {subtitle ? (
            <p className="app-header-subtitle subtle" id="app-header-subtitle">
              {subtitle}
            </p>
          ) : null}
        </div>
      </div>
      {children ? <div className="app-header-actions">{children}</div> : null}
    </header>
  );
}
