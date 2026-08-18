import Ajv from "ajv";
import type { Class2MockFixture } from "../contracts/class2Mock";
import { fixtureCatalog, mockFixtureNames, type MockFixtureName } from "./fixtures";
import schema from "./schema/class2-mock-view.schema.json";

const ajv = new Ajv({ allErrors: true, strict: true, strictRequired: false });
const validateFixture = ajv.compile<Class2MockFixture>(schema);

function isMockFixtureName(value: string): value is MockFixtureName {
  return mockFixtureNames.some((fixtureName) => fixtureName === value);
}

export function validateDevelopmentFixture(
  value: unknown,
  fixtureName: string,
): Class2MockFixture {
  if (!validateFixture(value)) {
    const detail = ajv.errorsText(validateFixture.errors, { separator: "; " });
    throw new Error(`Invalid development fixture ${fixtureName}: ${detail}`);
  }

  return value;
}

export function loadDevelopmentMock(fixtureName: string): Class2MockFixture {
  if (!isMockFixtureName(fixtureName)) {
    throw new Error(`Unknown development fixture: ${fixtureName}`);
  }

  return validateDevelopmentFixture(fixtureCatalog[fixtureName], fixtureName);
}
