import type { Class3MockFixture } from "../contracts/class3Mock";
import { fixtureCatalog, type MockFixtureName } from "./fixtures";

export function loadDevelopmentMock(fixtureName: string): Class3MockFixture {
  if (!Object.hasOwn(fixtureCatalog, fixtureName)) {
    throw new Error(`Unknown development fixture: ${fixtureName}`);
  }

  return fixtureCatalog[fixtureName as MockFixtureName];
}
