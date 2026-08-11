// @vitest-environment node

import Ajv from "ajv";
import { describe, expect, it } from "vitest";
import { releaseStatuses } from "../contracts/class3Mock";
import { fixtureCatalog } from "../mock/fixtures";
import schema from "../mock/schema/class3-mock-view.schema.json";

const ajv = new Ajv({ allErrors: true, strict: true, strictRequired: false });
const validate = ajv.compile(schema);

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

  it("provides exactly one fixture for each required release state", () => {
    expect(Object.keys(fixtureCatalog).sort()).toEqual([...releaseStatuses].sort());
  });

  it("keeps product-group and product-name selection types distinct", () => {
    const types = fixtureCatalog.released.selection_summary.selections.map(
      (selection) => selection.type,
    );
    expect(types).toContain("product_group");
    expect(types).toContain("product_name");
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
    const invalid = structuredClone(fixtureCatalog.released) as unknown as Record<
      string,
      unknown
    >;
    delete invalid.synthetic;
    expect(validate(invalid)).toBe(false);
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
