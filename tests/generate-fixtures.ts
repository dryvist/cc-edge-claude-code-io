/**
 * One-off fixture-generation helper.
 *
 * Usage (with the typescript devShell + Cribl up at localhost:9000):
 *
 *   node --experimental-strip-types tests/generate-fixtures.ts \
 *     <pipeline-name> <input-fixture-path>
 *
 * Reads the input fixture, runs it through the named pipeline against the
 * live Cribl Stream container, trims the output to partial-match-friendly
 * keys (sourcetype, index, datatype, _raw, _time), and writes the result
 * to <input-fixture-path-without-.json>.expected.json next to the input.
 *
 * Lives in tests/ as a committed artifact per the dryvist no-throwaway-scripts
 * rule. Re-run any time fixtures need to be regenerated against a new pack
 * version.
 */

import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { CriblClient, type CriblEvent, getPackId, PACK_ROOT } from './cribl-client.js';

const PARTIAL_MATCH_KEYS = ['sourcetype', 'index', 'datatype', '_raw', '_time'] as const;

function trim(events: CriblEvent[]): CriblEvent[] {
  return events.map((event) => {
    const trimmed: CriblEvent = {};
    for (const key of PARTIAL_MATCH_KEYS) {
      if (key in event) trimmed[key] = event[key];
    }
    return trimmed;
  });
}

async function main(): Promise<void> {
  const [, , pipeline, inputPath] = process.argv;
  if (pipeline === undefined || inputPath === undefined) {
    console.error(
      'Usage: node --experimental-strip-types tests/generate-fixtures.ts <pipeline> <input-fixture-path>',
    );
    process.exit(1);
  }

  const absInput = resolve(inputPath);
  const filename = absInput.split('/').pop();
  if (filename === undefined) {
    throw new Error(`Could not derive filename from path '${absInput}'`);
  }
  const expectedPath = join(dirname(absInput), `${filename.replace(/\.json$/, '')}.expected.json`);

  const events = JSON.parse(await readFile(absInput, 'utf-8')) as CriblEvent[];
  console.log(`Loaded ${events.length} input event(s) from ${absInput}`);

  const client = new CriblClient({
    host: process.env.CRIBL_HOST,
    port: process.env.CRIBL_PORT !== undefined ? Number(process.env.CRIBL_PORT) : undefined,
    username: process.env.CRIBL_USER,
    password: process.env.CRIBL_PASS,
  });

  await client.waitUntilReady();
  console.log('Cribl is ready');

  const packId = getPackId();
  const tarball = await CriblClient.createPackTarball(PACK_ROOT);
  await client.installPack(tarball, packId);
  console.log(`Installed pack: ${packId}`);

  try {
    const sampleId = await client.saveSample(`fixture-${pipeline}`, events);
    const output = await client.runPipeline(pipeline, sampleId, { pack: packId });
    console.log(`Pipeline produced ${output.length} event(s)`);

    const trimmed = trim(output);
    await writeFile(expectedPath, `${JSON.stringify(trimmed, null, 2)}\n`);
    console.log(`Wrote expected fixture: ${expectedPath}`);

    await client.deleteSample(sampleId);
  } finally {
    try {
      await client.deletePack(packId);
    } catch {
      // best-effort
    }
  }
}

await main();
