/**
 * Vitest globalSetup — runs once per test session, before all test files.
 *
 * Connects to the Cribl container, builds + installs this pack, exposes the
 * pack id via env var so test files can reuse it. The token is NOT shared
 * across processes; each test file's CriblClient re-authenticates on first
 * use (cheap — one HTTP call).
 */

import { CriblClient, getPackId, PACK_ROOT } from './cribl-client.js';

export async function setup(): Promise<void> {
  const packId = getPackId();
  process.env.CRIBL_PACK_ID = packId;

  const client = new CriblClient({
    host: process.env.CRIBL_HOST,
    port: process.env.CRIBL_PORT !== undefined ? Number(process.env.CRIBL_PORT) : undefined,
    username: process.env.CRIBL_USER,
    password: process.env.CRIBL_PASS,
  });

  await client.waitUntilReady();
  const tarball = await CriblClient.createPackTarball(PACK_ROOT);
  await client.installPack(tarball, packId);
}

export async function teardown(): Promise<void> {
  const packId = process.env.CRIBL_PACK_ID;
  if (packId === undefined) return;

  const client = new CriblClient({
    host: process.env.CRIBL_HOST,
    port: process.env.CRIBL_PORT !== undefined ? Number(process.env.CRIBL_PORT) : undefined,
    username: process.env.CRIBL_USER,
    password: process.env.CRIBL_PASS,
  });

  try {
    await client.deletePack(packId);
  } catch {
    // best-effort cleanup
  }
  try {
    await client.deleteAllSamples();
  } catch {
    // best-effort cleanup
  }
}
