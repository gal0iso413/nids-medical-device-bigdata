/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CLASS2_DATA_SOURCE?: string;
  readonly VITE_CLASS2_MOCK_FIXTURE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
