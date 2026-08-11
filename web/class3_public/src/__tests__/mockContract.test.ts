// @vitest-environment node

import Ajv from "ajv";
import { describe, expect, it } from "vitest";
import {
  releaseStatuses,
  viewStates,
  type Class3MockFixture,
} from "../contracts/class3Mock";
import { validateDevelopmentFixture } from "../mock/developmentAdapter";
import { fixtureCatalog, mockFixtureNames } from "../mock/fixtures";
import schema from "../mock/schema/class3-mock-view.schema.json";

const ajv = new Ajv({ allErrors: true, strict: true, strictRequired: false });
const validate = ajv.compile<Class3MockFixture>(schema);

function collectKeys(value: unknown, keys: string[] = []): string[] {
  if (Array.isArray(value)) {
    value.forEach((item) => collectKeys(item, keys));
    return keys;
  }

  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, nested]) => {
      keys.push(key);
      collectKeys(nested, keys);
    });
  }

  return keys;
}

describe("Class 3 development mock contract", () => {
  it("validates every fixture against the versioned JSON Schema", () => {
    for (const [name, fixture] of Object.entries(fixtureCatalog)) {
      const valid = validate(fixture);
      expect(validate.errors, `${name}: ${JSON.stringify(validate.errors)}`).toBeNull();
      expect(valid).toBe(true);
    }
  });

  it("defines exactly the six approved release statuses", () => {
    expect(releaseStatuses).toEqual([
      "released",
      "suppressed_small_cell",
      "suppressed_dominance",
      "suppressed_differencing",
      "insufficient_coverage",
      "not_available",
    ]);
    expect(releaseStatuses).not.toContain("empty");
  });

  it("defines results and empty as view states, not release states", () => {
    expect(viewStates).toEqual(["results", "empty"]);
    expect(fixtureCatalog.released.view_state).toBe("results");
    expect(mockFixtureNames).toEqual([
      "released",
      "suppressed_small_cell",
      "suppressed_dominance",
      "suppressed_differencing",
      "insufficient_coverage",
      "not_available",
      "empty",
    ]);
    expect(Object.keys(fixtureCatalog)).toEqual([...mockFixtureNames]);
  });

  it("keeps item-group and item-name selection types distinct", () => {
    const types = fixtureCatalog.released.selection_summary.selections.map(
      (selection) => selection.type,
    );
    expect(types).toContain("item_group");
    expect(types).toContain("item_name");
  });

  it("keeps per-item results and portfolio summary as separate structures", () => {
    const fixture = fixtureCatalog.released;
    expect(Array.isArray(fixture.per_item_results)).toBe(true);
    expect(Array.isArray(fixture.portfolio_summary)).toBe(false);
    expect(fixture.portfolio_summary).not.toBe(fixture.per_item_results);
  });

  it("does not include releasable content in suppressed fixtures", () => {
    const suppressed = [
      fixtureCatalog.suppressed_small_cell,
      fixtureCatalog.suppressed_dominance,
      fixtureCatalog.suppressed_differencing,
    ];

    for (const fixture of suppressed) {
      const keys = collectKeys(fixture);
      expect(keys).not.toContain("released_content");
      expect(keys).not.toContain("released_composition");
      expect(keys).not.toContain("released_stages");
    }
  });

  it("contains no forbidden direct-identifier fields", () => {
    const forbidden = new Set([
      "company_name",
      "business_registration_number",
      "company_serial",
      "hospital_code",
      "provider_identifier",
      "recipient_identifier",
    ]);

    for (const fixture of Object.values(fixtureCatalog)) {
      const keys = collectKeys(fixture);
      expect(keys.filter((key) => forbidden.has(key))).toEqual([]);
    }
  });

  it("rejects a fixture without the synthetic marker", () => {
    const { synthetic: _synthetic, ...invalid } = structuredClone(
      fixtureCatalog.released,
    );
    expect(validate(invalid)).toBe(false);
    expect(() => validateDevelopmentFixture(invalid, "missing-synthetic")).toThrow(
      "Invalid development fixture missing-synthetic",
    );
  });

  it("keeps the empty fixture value-free and separate from release status", () => {
    const fixture = validateDevelopmentFixture(fixtureCatalog.empty, "empty");
    expect(fixture.view_state).toBe("empty");
    expect(fixture.release_status).toBe("released");
    expect(fixture.per_item_results).toEqual([]);
    expect(fixture.portfolio_summary.release_status).toBe("not_available");
    expect(fixture.observed_reach.release_status).toBe("not_available");
    expect(fixture.coverage.release_status).toBe("not_available");
    expect(collectKeys(fixture)).not.toContain("released_content");
    expect(collectKeys(fixture)).not.toContain("released_composition");
    expect(collectKeys(fixture)).not.toContain("released_stages");
  });

  it("does not define additive quantity or cross-item HHI fields", () => {
    const forbiddenAggregateKeys = new Set([
      "hhi",
      "combined_hhi",
      "quantity_sum",
      "combined_quantity",
      "amount",
      "amount_sum",
    ]);

    for (const fixture of Object.values(fixtureCatalog)) {
      const keys = collectKeys(fixture);
      expect(keys.filter((key) => forbiddenAggregateKeys.has(key))).toEqual([]);
    }
  });
});
