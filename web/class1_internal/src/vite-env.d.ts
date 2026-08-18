/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CLASS1_DATA_SOURCE?: string;
  readonly VITE_CLASS1_HANDOFF_URL?: string;
  readonly VITE_CLASS1_API_BASE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
