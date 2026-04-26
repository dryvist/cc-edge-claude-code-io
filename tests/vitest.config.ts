import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Single sequential worker — pack install is shared across files via globalSetup.
    fileParallelism: false,
    globalSetup: ["./global-setup.ts"],
    testTimeout: 60_000,
    hookTimeout: 120_000,
    reporters: ["verbose"],
  },
});
