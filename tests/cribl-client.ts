/**
 * Cribl management API client for pack testing.
 *
 * TypeScript port of the criblpacks/cribl-palo-alto-networks pattern.
 * Streamlined for Vitest-based fixture testing.
 *
 * References:
 * - https://docs.cribl.io/api-reference/
 * - https://github.com/criblpacks/cribl-palo-alto-networks
 */

import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { readdir, readFile } from "node:fs/promises";
import * as path from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import { create as tarCreate } from "tar";
import { parse as yamlParse } from "yaml";
import { parseSimpleFilter } from "./parse-filter.js";

// PACK_ROOT is the directory containing default/, data/, package.json — i.e.
// one level up from this tests/ folder.
export const PACK_ROOT = path.resolve(import.meta.dirname, "..");

export interface CriblClientOptions {
  host?: string | undefined;
  port?: number | undefined;
  username?: string | undefined;
  password?: string | undefined;
  scheme?: "http" | "https" | undefined;
}

export interface CriblEvent {
  [key: string]: unknown;
}

export interface Route {
  id?: string;
  name?: string;
  pipeline: string;
  filter?: string;
  output?: string;
  disabled?: boolean;
  [key: string]: unknown;
}

export interface RouteFlowResult {
  route: Route;
  pipeline: string;
  events: CriblEvent[];
}

export type PackType = "edge" | "stream";

const REQUIRED_FIELDS: Record<PackType, readonly string[]> = {
  edge: ["sourcetype", "index"],
  stream: ["host", "source", "_time"],
};

// Cribl pack contents — only these top-level entries (mix of directories
// and files) ship inside the .crbl. Whitelisting keeps the tarball stable
// as repo-level dev tooling (flake.nix, biome.jsonc, etc.) accumulates.
// node-tar's create() recurses into the directory entries automatically and
// emits proper directory headers (Cribl rejects tarballs missing them).
const PACK_ROOT_ENTRIES = new Set([
  "data",
  "default",
  "package.json",
  "README.md",
  "LICENSE",
]);

export class CriblClient {
  readonly host: string;
  readonly port: number;
  readonly username: string;
  readonly password: string;
  readonly scheme: string;
  private cachedToken: string | null = null;

  constructor(options: CriblClientOptions = {}) {
    this.host = options.host ?? "localhost";
    this.port = options.port ?? 9000;
    this.username = options.username ?? "admin";
    this.password = options.password ?? "admin";
    this.scheme = options.scheme ?? "http";
  }

  get baseUrl(): string {
    return `${this.scheme}://${this.host}:${this.port}/api/v1`;
  }

  private async login(): Promise<string> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        username: this.username,
        password: this.password,
      }),
    });
    if (!response.ok) {
      throw new Error(
        `Cribl login failed: HTTP ${response.status} ${await response.text()}`,
      );
    }
    const body = (await response.json()) as { token: string };
    return body.token;
  }

  async token(): Promise<string> {
    if (this.cachedToken === null) {
      this.cachedToken = await this.login();
    }
    return this.cachedToken;
  }

  /**
   * Send an authenticated HTTP request to the Cribl management API.
   *
   * The `pack` option scopes the URL to `/p/<pack>/<endpoint>` (matches
   * Cribl's pack-namespaced preview routes).
   */
  async call(
    method: string,
    endpoint: string,
    options: {
      pack?: string | undefined;
      payload?: unknown;
      body?: string | Uint8Array | undefined;
      params?: Record<string, string | number> | undefined;
      authenticated?: boolean | undefined;
      contentType?: string | undefined;
    } = {},
  ): Promise<unknown> {
    const prefix = options.pack !== undefined ? `/p/${options.pack}` : "";
    const search =
      options.params !== undefined
        ? `?${new URLSearchParams(
            Object.fromEntries(
              Object.entries(options.params).map(([k, v]) => [k, String(v)]),
            ),
          ).toString()}`
        : "";
    const url = `${this.baseUrl}${prefix}${endpoint}${search}`;

    const headers: Record<string, string> = {};
    if (options.authenticated !== false) {
      headers.authorization = `Bearer ${await this.token()}`;
    }

    let body: string | Uint8Array | undefined;
    if (options.payload !== undefined) {
      headers["content-type"] = options.contentType ?? "application/json";
      body = JSON.stringify(options.payload);
    } else if (options.body !== undefined) {
      headers["content-type"] =
        options.contentType ?? "application/octet-stream";
      body = options.body;
    }

    const init: RequestInit = { method: method.toUpperCase(), headers };
    if (body !== undefined) init.body = body;
    const response = await fetch(url, init);
    const text = await response.text();

    if (!response.ok) {
      throw new Error(
        `Cribl API ${method.toUpperCase()} ${endpoint} failed: HTTP ${response.status} ${response.statusText} — ${text || "<empty body>"}`,
      );
    }

    // Try JSON first; fall back to NDJSON; fall back to raw text.
    if (text.length === 0) return null;
    try {
      return JSON.parse(text);
    } catch {
      // NDJSON (newline-delimited)
      const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
      try {
        return lines.map((line) => JSON.parse(line));
      } catch {
        return text;
      }
    }
  }

  // ---- Lifecycle -------------------------------------------------------

  async waitUntilReady(timeoutSeconds = 120): Promise<void> {
    const deadline = Date.now() + timeoutSeconds * 1000;
    let lastError: unknown;
    while (Date.now() < deadline) {
      try {
        const response = await fetch(`${this.baseUrl}/health`);
        if (response.status === 200) return;
      } catch (err) {
        lastError = err;
      }
      await sleep(2000);
    }
    throw new Error(
      `Cribl at ${this.baseUrl} did not become ready in ${timeoutSeconds}s (last error: ${String(lastError)})`,
    );
  }

  // ---- Pack management -------------------------------------------------

  /**
   * Build an in-memory .crbl tarball from packRoot, excluding test/dev directories.
   */
  static async createPackTarball(packRoot: string): Promise<Buffer> {
    const entries = await collectTarballEntries(packRoot);
    const stream = tarCreate(
      {
        gzip: true,
        cwd: packRoot,
        portable: true,
        // Normalize ownership so the tarball is deterministic.
        mtime: new Date(0),
      },
      entries,
    );
    const chunks: Buffer[] = [];
    for await (const chunk of stream) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    return Buffer.concat(chunks);
  }

  /**
   * Upload a .crbl tarball, install it, and (optionally) wait for it to register.
   *
   * Cribl's pack install is asynchronous — the POST returns before the pack
   * is fully registered. If `expectedId` is provided, poll /packs until it
   * appears (or throw on timeout). Without `expectedId`, returns immediately
   * after the install POST.
   */
  async installPack(
    tarball: Buffer,
    expectedId?: string,
    timeoutSeconds = 30,
  ): Promise<void> {
    const filename = `${randomUUID()}.crbl`;
    const upload = await this.call("put", "/packs", {
      params: { filename, size: tarball.length },
      body: new Uint8Array(tarball),
    });
    if (upload !== null && upload !== undefined) {
      await this.call("post", "/packs", { payload: upload });
    }

    if (expectedId === undefined) return;

    const deadline = Date.now() + timeoutSeconds * 1000;
    let installed: (string | undefined)[] = [];
    while (Date.now() < deadline) {
      installed = (await this.listPacks()).map((p) => p.id);
      if (installed.includes(expectedId)) return;
      await sleep(500);
    }
    throw new Error(
      `Pack '${expectedId}' did not appear in /packs after ${timeoutSeconds}s. Currently installed: ${JSON.stringify(installed)}`,
    );
  }

  async deletePack(packId: string): Promise<void> {
    const info = await this.call("get", `/packs/${packId}`);
    if (info !== null && info !== undefined) {
      await this.call("delete", `/packs/${packId}`, { payload: info });
    }
  }

  async listPacks(): Promise<{ id?: string }[]> {
    const response = await this.call("get", "/packs");
    if (
      response !== null &&
      typeof response === "object" &&
      "items" in response
    ) {
      const items = (response as { items: unknown }).items;
      if (Array.isArray(items)) return items as { id?: string }[];
    }
    return [];
  }

  // ---- Sample lifecycle -----------------------------------------------

  async saveSample(name: string, events: CriblEvent[]): Promise<string> {
    const response = (await this.call("post", "/system/samples", {
      payload: { sampleName: name, context: { events } },
    })) as { items: { id: string }[] };
    if (response.items[0] === undefined) {
      throw new Error(`saveSample('${name}') returned no items`);
    }
    return response.items[0].id;
  }

  async deleteSample(sampleId: string): Promise<void> {
    const info = await this.call("get", `/system/samples/${sampleId}`);
    if (
      info !== null &&
      typeof info === "object" &&
      "items" in info &&
      Array.isArray((info as { items: unknown }).items) &&
      (info as { items: unknown[] }).items.length > 0
    ) {
      await this.call("delete", `/system/samples/${sampleId}`, {
        payload: (info as { items: unknown[] }).items[0],
      });
    }
  }

  async deleteAllSamples(): Promise<void> {
    const response = await this.call("get", "/system/samples");
    if (
      response === null ||
      typeof response !== "object" ||
      !("items" in response)
    )
      return;
    const items = (response as { items: unknown[] }).items;
    if (!Array.isArray(items)) return;
    for (const sample of items) {
      if (
        sample !== null &&
        typeof sample === "object" &&
        "isTemplate" in sample
      )
        continue;
      const id = (sample as { id?: string }).id;
      if (id !== undefined) {
        await this.call("delete", `/system/samples/${id}`, { payload: sample });
      }
    }
  }

  // ---- Pipeline execution ---------------------------------------------

  async runPipeline(
    pipeline: string,
    sampleId: string,
    options: {
      pack?: string | undefined;
      timeoutMs?: number;
      memoryMb?: number;
    } = {},
  ): Promise<CriblEvent[]> {
    const response = await this.call("post", "/preview", {
      pack: options.pack,
      payload: {
        mode: "pipe",
        pipelineId: pipeline,
        level: 3,
        sampleId,
        dropped: true,
        cpuProfile: false,
        timeout: options.timeoutMs ?? 10_000,
        memory: options.memoryMb ?? 2048,
      },
    });
    if (
      response !== null &&
      typeof response === "object" &&
      "items" in response
    ) {
      const items = (response as { items: unknown }).items;
      if (Array.isArray(items)) return items as CriblEvent[];
    }
    if (Array.isArray(response)) return response as CriblEvent[];
    return [];
  }

  // ---- Route flow + assertions ----------------------------------------

  /**
   * Match events against route.yml filters, then execute the matched pipeline.
   *
   * Cribl's `/preview` API has no `mode: "route"` — this is the local
   * fallback. Loads `PACK_ROOT/default/pipelines/route.yml`, evaluates each
   * non-disabled route's filter via `parseSimpleFilter` (canonical
   * `<field>=='<value>'` matcher), and on the first match calls
   * `runPipeline` for that route's pipeline.
   *
   * Throws if no route matches (lists any filters skipped because the local
   * matcher doesn't support them, so the caller can decide whether to skip
   * the test vs treat it as a real failure).
   */
  async runRouteFlow(
    sampleId: string,
    events: CriblEvent[],
    options: { pack?: string | undefined } = {},
  ): Promise<RouteFlowResult> {
    const routeYml = path.join(PACK_ROOT, "default", "pipelines", "route.yml");
    const config = yamlParse(await readFile(routeYml, "utf-8")) as {
      routes?: Route[];
    };

    const skippedFilters: string[] = [];
    for (const route of config.routes ?? []) {
      if (route.disabled === true) continue;
      const parsed = parseSimpleFilter(route.filter);
      if (parsed === null) {
        skippedFilters.push(route.filter ?? "");
        continue;
      }
      const [field, expectedValue] = parsed;
      const matches = events.some((event) => event[field] === expectedValue);
      if (matches) {
        const output = await this.runPipeline(
          route.pipeline,
          sampleId,
          options,
        );
        return { route, pipeline: route.pipeline, events: output };
      }
    }

    throw new Error(
      `No matching route for given events. Filters skipped (unparseable by local matcher): ${JSON.stringify(skippedFilters)}`,
    );
  }

  /**
   * Assert every event has the canonical output fields for its pack type.
   *
   * Edge packs require `sourcetype` + `index` (Splunk-canonical routing fields).
   * Stream packs require `host` + `source` + `_time`.
   *
   * When `packType` is undefined, infer from `package.json` name prefix.
   */
  static assertRequiredFields(events: CriblEvent[], packType?: PackType): void {
    const resolvedType = packType ?? detectPackType();
    const required = REQUIRED_FIELDS[resolvedType];

    const violations: string[] = [];
    for (const [i, event] of events.entries()) {
      const missing = required.filter((field) => !(field in event));
      if (missing.length > 0) {
        violations.push(`event ${i}: missing ${JSON.stringify(missing)}`);
      }
    }

    if (violations.length > 0) {
      throw new Error(
        `${resolvedType} pack required fields ${JSON.stringify(required)} missing from ${violations.length}/${events.length} event(s):\n  ${violations.join("\n  ")}`,
      );
    }
  }

  // ---- Live capture (primitives reserved for future integration tests) -

  async startCapture(
    filterExpr: string,
    maxEvents = 100,
    timeoutMs = 30_000,
  ): Promise<string> {
    const response = await this.call("post", "/lib/captures", {
      payload: { filter: filterExpr, maxEvents, timeout: timeoutMs, level: 0 },
    });
    if (
      response === null ||
      typeof response !== "object" ||
      !("captureId" in response)
    ) {
      throw new Error(
        `Unexpected capture response: ${JSON.stringify(response)}`,
      );
    }
    return (response as { captureId: string }).captureId;
  }

  async readCapture(
    captureId: string,
    options: { pollIntervalMs?: number; timeoutSeconds?: number } = {},
  ): Promise<CriblEvent[]> {
    const pollIntervalMs = options.pollIntervalMs ?? 1000;
    const timeoutSeconds = options.timeoutSeconds ?? 60;
    const deadline = Date.now() + timeoutSeconds * 1000;
    while (Date.now() < deadline) {
      const response = await this.call(
        "get",
        `/lib/captures/${captureId}/events`,
      );
      if (
        response !== null &&
        typeof response === "object" &&
        "status" in response &&
        (response as { status: string }).status === "complete"
      ) {
        const items = (response as { items?: unknown }).items;
        return Array.isArray(items) ? (items as CriblEvent[]) : [];
      }
      await sleep(pollIntervalMs);
    }
    throw new Error(
      `Capture ${captureId} did not complete in ${timeoutSeconds}s`,
    );
  }
}

/**
 * Infer pack type from the pack root's package.json name field.
 */
export function detectPackType(): PackType {
  const pkg = JSON.parse(
    readFileSync(path.join(PACK_ROOT, "package.json"), "utf-8"),
  ) as {
    name?: string;
  };
  const name = pkg.name ?? "";
  if (name.startsWith("cc-edge-")) return "edge";
  if (name.startsWith("cc-stream-")) return "stream";
  throw new Error(
    `Cannot detect pack_type from package.json name '${name}'; expected 'cc-edge-<source>-io' or 'cc-stream-<source>-io' prefix.`,
  );
}

/**
 * Read the pack id (package.json name) — used by tests + setup.
 */
export function getPackId(): string {
  const pkg = JSON.parse(
    readFileSync(path.join(PACK_ROOT, "package.json"), "utf-8"),
  ) as {
    name?: string;
  };
  if (pkg.name === undefined || pkg.name.length === 0) {
    throw new Error('package.json missing required "name" field');
  }
  return pkg.name;
}

// ---- Internal helpers --------------------------------------------------

async function collectTarballEntries(packRoot: string): Promise<string[]> {
  const dirents = await readdir(packRoot, { withFileTypes: true });
  // Sort for determinism — readdir() ordering varies across filesystems.
  return dirents
    .filter((d) => PACK_ROOT_ENTRIES.has(d.name))
    .map((d) => d.name)
    .sort();
}
