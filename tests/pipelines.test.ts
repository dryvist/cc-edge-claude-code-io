/**
 * Pipeline tests — auto-discovered + parametrized over tests/fixtures/.
 *
 * GENERIC: copied verbatim from the template into every pack repo.
 *
 * Convention:
 *     tests/fixtures/<pipeline-name>/<case>.json          -- input event(s)
 *     tests/fixtures/<pipeline-name>/<case>.expected.json -- (optional) expected output
 *     tests/fixtures/.skip-required-fields                -- (optional) marker;
 *         when present, the required-fields assertion is bypassed for this pack
 *         (use for pass-through packs whose downstream sets sourcetype/index)
 *
 * For each fixture:
 * 1. Save the input as a Cribl sample.
 * 2. Run it through the named pipeline (within this pack's namespace).
 * 3. If <case>.expected.json exists, partial-match-assert each output event
 *    has the expected fields and values. Extra fields in actual output OK.
 * 4. If <case>.expected.json is absent, smoke-test only: assert non-empty.
 * 5. Unless `.skip-required-fields` is present, assert every output event
 *    has the canonical fields for this pack type.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import * as path from 'node:path';
import { describe, expect, it } from 'vitest';
import { CriblClient, type CriblEvent } from './cribl-client.js';
import { getInstalledPackId, makeClient } from './test-helpers.js';

const FIXTURES = path.join(import.meta.dirname, 'fixtures');
const SKIP_REQUIRED_FIELDS_MARKER = path.join(FIXTURES, '.skip-required-fields');

interface FixtureCase {
  pipeline: string;
  inputFile: string;
  expectedFile: string | null;
  id: string;
}

function discoverCases(): FixtureCase[] {
  if (!existsSync(FIXTURES)) return [];
  const cases: FixtureCase[] = [];
  for (const entry of readdirSync(FIXTURES, { withFileTypes: true }).sort((a, b) =>
    a.name.localeCompare(b.name),
  )) {
    if (!entry.isDirectory()) continue;
    const pipelineDir = path.join(FIXTURES, entry.name);
    const files = readdirSync(pipelineDir).sort();
    for (const file of files) {
      if (!file.endsWith('.json') || file.endsWith('.expected.json')) continue;
      const stem = file.slice(0, -'.json'.length);
      const expectedFile = path.join(pipelineDir, `${stem}.expected.json`);
      cases.push({
        pipeline: entry.name,
        inputFile: path.join(pipelineDir, file),
        expectedFile: existsSync(expectedFile) ? expectedFile : null,
        id: `${entry.name}/${stem}`,
      });
    }
  }
  return cases;
}

function loadEvents(filePath: string): CriblEvent[] {
  const raw = JSON.parse(readFileSync(filePath, 'utf-8')) as unknown;
  return Array.isArray(raw) ? (raw as CriblEvent[]) : [raw as CriblEvent];
}

function assertPartialMatch(actual: CriblEvent[], expected: CriblEvent[], context: string): void {
  expect(
    actual.length,
    `${context}: pipeline produced ${actual.length} events, expected ${expected.length}`,
  ).toBe(expected.length);
  for (let i = 0; i < expected.length; i++) {
    const act = actual[i];
    const exp = expected[i];
    if (act === undefined || exp === undefined) continue;
    for (const [key, expVal] of Object.entries(exp)) {
      expect(key in act, `${context} event ${i}: expected key '${key}' missing from output`).toBe(
        true,
      );
      expect(
        act[key],
        `${context} event ${i}, key '${key}': expected ${JSON.stringify(expVal)}, got ${JSON.stringify(act[key])}`,
      ).toEqual(expVal);
    }
  }
}

const CASES = discoverCases();
const SKIP_REQUIRED_FIELDS = existsSync(SKIP_REQUIRED_FIELDS_MARKER);

describe('pipeline behavior (fixture-driven)', () => {
  if (CASES.length === 0) {
    it.skip('no fixtures found in tests/fixtures/<pipeline>/', () => undefined);
    return;
  }

  for (const fixture of CASES) {
    it(`${fixture.id} processes its sample`, async () => {
      const events = loadEvents(fixture.inputFile);
      const client = makeClient();
      const packId = getInstalledPackId();
      const sampleId = await client.saveSample(path.basename(fixture.inputFile, '.json'), events);
      try {
        const result = await client.runPipeline(fixture.pipeline, sampleId, { pack: packId });

        expect(
          result.length,
          `Pipeline '${fixture.pipeline}' produced no output for ${path.basename(fixture.inputFile)}. Check the pipeline's filter/drop conditions.`,
        ).toBeGreaterThan(0);

        if (fixture.expectedFile !== null) {
          const expected = loadEvents(fixture.expectedFile);
          assertPartialMatch(result, expected, path.basename(fixture.inputFile));
        }

        if (!SKIP_REQUIRED_FIELDS) {
          CriblClient.assertRequiredFields(result);
        }
      } finally {
        await client.deleteSample(sampleId);
      }
    });
  }
});
