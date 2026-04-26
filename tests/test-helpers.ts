/**
 * Per-test-file Cribl client helper.
 *
 * Vitest's globalSetup runs in a separate process, so we can't share a token
 * — each test file constructs its own CriblClient that re-authenticates on
 * first use. The pack itself is already installed (from globalSetup); the
 * pack id flows via env var.
 */

import { CriblClient } from './cribl-client.js';

export function makeClient(): CriblClient {
  return new CriblClient({
    host: process.env.CRIBL_HOST,
    port: process.env.CRIBL_PORT !== undefined ? Number(process.env.CRIBL_PORT) : undefined,
    username: process.env.CRIBL_USER,
    password: process.env.CRIBL_PASS,
  });
}

export function getInstalledPackId(): string {
  const id = process.env.CRIBL_PACK_ID;
  if (id === undefined || id.length === 0) {
    throw new Error('CRIBL_PACK_ID env var is unset — globalSetup did not run or failed silently.');
  }
  return id;
}
