import Ajv from "ajv";
import type { Class3MockFixture } from "../contracts/class3Mock";
import { fixtureCatalog, mockFixtureNames, type MockFixtureName } from "./fixtures";
import schema from "./schema/class3-mock-view.schema.json";

const ajv = new Ajv({ allErrors: true, strict: true, strictRequired: false });
const validateFixture = ajv.compile<Class3MockFixture>(schema);

function isMockFixtureName(value: string): value is MockFixtureName {
  return mockFixtureNames.some((fixtureName) => fixtureName === value);
}

export function validateDevelopmentFixture(
  value: unknown,
  fixtureName: string,
): Class3MockFixture {
  if (!validateFixture(value)) {
    const detail = ajv.errorsText(validateFixture.errors, { separator: "; " });
    throw new Error(`Invalid development fixture ${fixtureName}: ${detail}`);
  }

  return value;
}

export function loadDevelopmentMock(fixtureName: string): Class3MockFixture {
  if (!isMockFixtureName(fixtureName)) {
    throw new Error(`Unknown development fixture: ${fixtureName}`);
  }

  return validateDevelopmentFixture(fixtureCatalog[fixtureName], fixtureName);
}
