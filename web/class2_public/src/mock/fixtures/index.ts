import empty from "./empty.json";
import insufficientCoverage from "./insufficient-coverage.json";
import notAvailable from "./not-available.json";
import released from "./released.json";
import suppressedDifferencing from "./suppressed-differencing.json";
import suppressedDominance from "./suppressed-dominance.json";
import suppressedSmallCell from "./suppressed-small-cell.json";

export const mockFixtureNames = [
  "released",
  "suppressed_small_cell",
  "suppressed_dominance",
  "suppressed_differencing",
  "insufficient_coverage",
  "not_available",
  "empty",
] as const;

export type MockFixtureName = (typeof mockFixtureNames)[number];

export const fixtureCatalog = {
  released,
  suppressed_small_cell: suppressedSmallCell,
  suppressed_dominance: suppressedDominance,
  suppressed_differencing: suppressedDifferencing,
  insufficient_coverage: insufficientCoverage,
  not_available: notAvailable,
  empty,
} satisfies Record<MockFixtureName, unknown>;
