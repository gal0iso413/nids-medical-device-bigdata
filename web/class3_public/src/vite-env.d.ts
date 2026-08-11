/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CLASS3_DATA_SOURCE?: string;
  readonly VITE_CLASS3_MOCK_FIXTURE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
