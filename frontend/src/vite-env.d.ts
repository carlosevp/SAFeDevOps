/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_TITLE?: string;
  /** Public URL to PNG/SVG in `public/` or elsewhere. Set to empty string to hide the logo image. */
  readonly VITE_APP_LOGO_URL?: string;
  /** FastAPI base URL for production (e.g. https://xxx.up.railway.app). Omit for dev (Vite proxy). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
