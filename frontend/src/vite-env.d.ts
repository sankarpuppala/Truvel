/// <reference types="vite/client" />

/** The only build-time flag the app reads (SPEC §8.7, AC-25). */
interface ImportMetaEnv {
  readonly VITE_DEV_TOOLS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
