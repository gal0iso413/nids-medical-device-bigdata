import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import ApiModeApp from "./ApiModeApp";
import { createClass1LookupAdapter } from "./apiLookupAdapter";
import "./styles.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element is missing.");

async function render() {
  if (import.meta.env.VITE_CLASS1_DATA_SOURCE === "api") {
    try {
      const adapter = createClass1LookupAdapter(import.meta.env.VITE_CLASS1_API_BASE || "/api");
      const status = await adapter.status();
      createRoot(rootElement).render(
        <StrictMode>
          <ApiModeApp adapter={adapter} status={status} />
        </StrictMode>,
      );
      return;
    } catch {
      createRoot(rootElement).render(
        <StrictMode>
          <main id="main-content" className="shell empty-state" tabIndex={-1}>
            <h1>내부 분석 데이터를 표시할 수 없습니다</h1>
            <p>로컬 조회 API에 연결하지 못했습니다. mock fallback은 사용하지 않습니다.</p>
          </main>
        </StrictMode>,
      );
      return;
    }
  }
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void render();
