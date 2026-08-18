// @vitest-environment node

import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function listRuntimeFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__tests__" || entry.name === "test") {
        return [];
      }
      return listRuntimeFiles(path);
    }
    return /\.(css|json|ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

describe("runtime dependency boundary", () => {
  it("does not depend on prototype, legacy Class 3, or fake API paths", () => {
    const forbiddenPatterns = [
      "prototype_meeting",
      "innovation/class3",
      "class_3_impact_evaluation",
      "run_mcdm_eda",
      'fetch("/api',
      "fetch('/api",
    ];

    for (const runtimePath of listRuntimeFiles(resolve(process.cwd(), "src"))) {
      const source = readFileSync(runtimePath, "utf8");
      for (const pattern of forbiddenPatterns) {
        expect(source, `${runtimePath} contains ${pattern}`).not.toContain(pattern);
      }
    }
  });

  it("does not load external stylesheets from CSS", () => {
    for (const runtimePath of listRuntimeFiles(resolve(process.cwd(), "src"))) {
      if (!runtimePath.endsWith(".css")) {
        continue;
      }
      const source = readFileSync(runtimePath, "utf8");
      expect(source, `${runtimePath} contains an external CSS import`).not.toMatch(
        /@import\s+(?:url\()?['"]?https?:\/\//i,
      );
    }
  });

  it("keeps the approved package dependency set", () => {
    const packageJson = JSON.parse(
      readFileSync(resolve(process.cwd(), "package.json"), "utf8"),
    ) as {
      dependencies: Record<string, string>;
      devDependencies: Record<string, string>;
    };

    expect(Object.keys(packageJson.dependencies).sort()).toEqual([
      "react",
      "react-dom",
    ]);
    expect(Object.keys(packageJson.devDependencies).sort()).toEqual([
      "@testing-library/jest-dom",
      "@testing-library/react",
      "@types/node",
      "@types/react",
      "@types/react-dom",
      "@vitejs/plugin-react",
      "ajv",
      "jsdom",
      "typescript",
      "vite",
      "vitest",
    ]);
  });
});
