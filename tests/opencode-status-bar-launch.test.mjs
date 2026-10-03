// Tests that the plugin opens the menu bar app when OpenCode starts.
// Run with: node --test --experimental-test-module-mocks
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { mock } from "node:test";

const home = await mkdtemp(join(tmpdir(), "status-bar-launch-test-"));
process.env.HOME = home;

const calls = [];
let nextExitCode = 0;
let throwOnSpawn = false;
mock.module("node:child_process", {
  namedExports: {
    spawn(command, args, options) {
      if (throwOnSpawn) throw new Error("spawn failed");
      calls.push({ command, args, options });
      const child = new EventEmitter();
      child.unref = () => {};
      const code = nextExitCode;
      setImmediate(() => child.emit("exit", code));
      return child;
    },
  },
});
const { default: plugin } = await import("../integrations/opencode-status-bar.js");

const LAUNCHED = Symbol.for("opencode-status-bar.launched");
const APP = join(home, "Applications", "OpenCode Status Bar.app");
const BY_ID = ["-g", "-b", "io.github.haoyangzhang99.OpenCodeStatusBar"];
const optOut = join(home, ".config", "opencode-status-bar", "no-autolaunch");
const failing = () => { throw new Error("offline"); };
const skip = process.platform !== "darwin" && "the app only exists on macOS";

async function load(directory = "/project") {
  const dispose = await plugin.setup({ location: { directory }, event: { subscribe: failing }, session: { get: failing } });
  await dispose();
}
const settle = () => new Promise((resolve) => setImmediate(() => setImmediate(resolve)));

test.beforeEach(async () => {
  calls.length = 0;
  nextExitCode = 0;
  throwOnSpawn = false;
  delete globalThis[LAUNCHED];
  await rm(optOut, { force: true });
});
test.after(() => rm(home, { recursive: true, force: true }));

test("opens the app in the background once per OpenCode process", { skip }, async () => {
  await load("/one");
  await load("/two");
  await settle();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].command, "/usr/bin/open");
  assert.deepEqual(calls[0].args, BY_ID);
  assert.equal(calls[0].options.detached, true);
  assert.equal(calls[0].options.stdio, "ignore");
});

test("falls back to the install path if the app ID is unknown", { skip }, async () => {
  nextExitCode = 1;
  await load();
  await settle();
  assert.deepEqual(calls.map((c) => c.args), [BY_ID, ["-g", APP]]);
});

test("the opt-out file disables launching", { skip }, async () => {
  await mkdir(join(home, ".config", "opencode-status-bar"), { recursive: true });
  await writeFile(optOut, "");
  await load();
  await settle();
  assert.equal(calls.length, 0);
});

test("a launch failure never breaks plugin startup", { skip }, async () => {
  throwOnSpawn = true;
  await assert.doesNotReject(load());
});
