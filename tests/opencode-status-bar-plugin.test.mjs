import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { setImmediate as immediate } from "node:timers/promises";
import test from "node:test";
import plugin from "../integrations/opencode-status-bar.js";

// Run all plugin code with an isolated HOME, never the user's monitor directory.
if (!process.env.MONITOR_PLUGIN_TEST_CHILD) {
  test("plugin suite in isolated HOME", async () => {
    const home = await mkdtemp(join(tmpdir(), "monitor-plugin-test-"));
    try {
      // Opt out of opening the real menu bar app; launching has its own tests.
      await mkdir(join(home, ".config", "opencode-status-bar"), { recursive: true });
      await writeFile(join(home, ".config", "opencode-status-bar", "no-autolaunch"), "");
      const env = { ...process.env, HOME: home, MONITOR_PLUGIN_TEST_CHILD: "1" };
      delete env.NODE_TEST_CONTEXT;
      const child = spawn(process.execPath, ["--test", fileURLToPath(import.meta.url)], {
        env,
        stdio: ["ignore", "pipe", "pipe"],
      });
      let output = "";
      child.stdout.on("data", (chunk) => { output += chunk; });
      child.stderr.on("data", (chunk) => { output += chunk; });
      const code = await new Promise((resolve, reject) => {
        child.on("error", reject);
        child.on("exit", resolve);
      });
      assert.equal(code, 0, output);
      console.log(output);
    } finally {
      await rm(home, { recursive: true, force: true });
    }
  });
} else {
  const parent = join(homedir(), ".config", "opencode-status-bar", "bridge");
  test.beforeEach(() => rm(parent, { recursive: true, force: true }));
  const directory = "/test/project";
  const filename = (dir = directory) => join(parent,
    `${process.pid}-${createHash("sha256").update(dir).digest("hex")}.json`);
  const snapshot = async (dir) => JSON.parse(await readFile(filename(dir), "utf8"));
  const absent = async (path) => stat(path).then(() => false, (error) => {
    if (error.code === "ENOENT") return true;
    throw error;
  });
  async function until(check) {
    const deadline = performance.now() + 3_000;
    while (performance.now() < deadline) {
      if (await check()) return;
      await immediate();
    }
    assert.fail("Timed out waiting for test condition");
  }
  async function setup(t, dir = directory) {
    t.mock.timers.enable({ apis: ["Date", "setTimeout"], now: 1_000_000 });
    const state = {
      statuses: { active: { type: "busy" } }, questions: [], permissions: [], listed: [],
      details: { active: { id: "active", title: "Session", directory: dir } },
      calls: [], failure: false, hang: false, signals: [],
    };
    const request = async (kind, options) => {
      state.calls.push(kind);
      state.signals.push(options.signal);
      assert.equal(options.query.directory, dir);
      assert.equal(options.throwOnError, true);
      if (state.failKind === kind) throw new Error("private endpoint failure");
      if (kind === "statuses" && state.hang) return new Promise((resolve) => { state.release = resolve; });
      if (kind === "statuses" && state.failure) return { error: { message: "private failure" } };
      if (kind === "listed") assert.equal(options.query.start, Date.now() - 60_000);
      if (kind === "details") assert.deepEqual(Object.keys(options.path), ["id"]);
      return { data: kind === "details" ? state.details[options.path.id] : state[kind] };
    };
    const client = {
      session: {
        status: (options) => request("statuses", options),
        list: (options) => request("listed", options),
        get: (options) => request("details", options),
      },
      _client: { get: (options) => {
        assert.ok(["/question", "/permission"].includes(options.url));
        return request(options.url === "/question" ? "questions" : "permissions", options);
      } },
    };
    const hooks = await plugin({ client, directory: dir });
    const dispose = () => hooks.event({ event: { type: "server.instance.disposed", properties: { directory: dir } } });
    t.after(dispose);
    await until(async () => !(await absent(filename(dir))));
    // Let the atomic-write cleanup finish and arm the next poll.
    await until(async () => (await readdir(parent)).every((name) => !name.endsWith(".tmp")));
    for (let i = 0; i < 20; i++) await immediate();
    return { state, hooks, dispose, client };
  }
  async function refresh(t, state) {
    const before = state.calls.length;
    const previous = (await snapshot()).updated;
    t.mock.timers.tick(2_000);
    await until(() => state.calls.length > before);
    await until(async () => (await snapshot()).updated > previous);
    for (let i = 0; i < 20; i++) await immediate();
  }

  test("only a default plugin export; exact sanitized contract and private atomic files", async (t) => {
    assert.deepEqual(Object.keys(await import("../integrations/opencode-status-bar.js")), ["default"]);
    const { state } = await setup(t);
    state.statuses = { active: { type: "retry", message: "secret retry message" } };
    state.questions = [{ sessionID: "active", questions: ["secret prompt"] }];
    state.permissions = [{ sessionID: "active", patterns: ["secret arguments"] }];
    Object.assign(state.details.active, { parentID: "parent", messages: ["secret"], password: "secret" });
    await refresh(t, state);
    assert.deepEqual(await snapshot(), {
      version: 1, pid: process.pid, updated: Date.now(), directory,
      sessions: [{ id: "active", title: "Session", directory, parentID: "parent", status: "retry",
        tools: [], question: true, permission: true }],
    });
    assert.equal((await stat(parent)).mode & 0o777, 0o700);
    assert.equal((await stat(filename())).mode & 0o777, 0o600);
    assert.equal((await readdir(parent)).length, 1);
  });

  test("retains completed sessions, includes recent idle and pending, excludes history and other directories", async (t) => {
    const { state } = await setup(t);
    state.statuses = {};
    state.listed = [
      { id: "recent", title: "Recent", directory, time: { updated: Date.now() } },
      { id: "old", title: "Old", directory, time: { updated: 1 } },
      { id: "foreign", title: "Foreign", directory: "/other", time: { updated: Date.now() } },
    ];
    state.questions = [{ sessionID: "pending" }, { sessionID: "foreign" }];
    state.details.pending = { id: "pending", title: "Pending", directory };
    await refresh(t, state);
    const sessions = (await snapshot()).sessions;
    assert.deepEqual(sessions.map((s) => s.id).sort(), ["active", "pending", "recent"]);
    assert.ok(sessions.every((s) => s.status === "idle"));
    assert.equal(sessions.find((s) => s.id === "pending").question, true);
    state.questions = [];
    t.mock.timers.tick(61_000);
    await until(async () => (await snapshot()).sessions.length === 0);
  });

  test("failed and malformed polls never freshen the last successful snapshot", async (t) => {
    const { state } = await setup(t);
    const original = await readFile(filename(), "utf8");
    state.failure = true;
    t.mock.timers.tick(2_000);
    await until(() => state.signals.at(-1).aborted);
    assert.equal(await readFile(filename(), "utf8"), original);
    state.failure = false;
    state.statuses = { active: { type: "unknown" } };
    const count = state.calls.length;
    t.mock.timers.tick(2_000);
    await until(() => state.calls.length > count && state.signals.at(-1).aborted);
    assert.equal(await readFile(filename(), "utf8"), original);
    state.statuses = {};
    await refresh(t, state);
    assert.equal((await snapshot()).sessions[0].status, "idle");
  });

  test("timeout aborts stuck polls without overlapping calls or refreshing stale data", async (t) => {
    const { state, dispose } = await setup(t);
    const original = await readFile(filename(), "utf8");
    state.hang = true;
    t.mock.timers.tick(2_000);
    await until(() => Boolean(state.release));
    const calls = state.calls.length;
    t.mock.timers.tick(5_000);
    await until(() => state.signals.at(-1).aborted);
    for (let i = 0; i < 20; i++) await immediate();
    t.mock.timers.tick(10_000);
    assert.equal(state.calls.length, calls);
    assert.equal(await readFile(filename(), "utf8"), original);
    await dispose();
    assert.ok(await absent(filename()));
    state.release({ data: state.statuses });
    for (let i = 0; i < 20; i++) await immediate();
    assert.ok(await absent(filename()));
  });

  test("pending endpoint failures fail closed rather than clearing pending flags", async (t) => {
    const { state } = await setup(t);
    state.questions = [{ sessionID: "active" }];
    state.permissions = [{ sessionID: "active" }];
    await refresh(t, state);
    const original = await readFile(filename(), "utf8");
    for (const kind of ["questions", "permissions"]) {
      state.failKind = kind;
      const count = state.calls.length;
      t.mock.timers.tick(2_000);
      await until(() => state.calls.length > count && state.signals.at(-1).aborted);
      assert.equal(await readFile(filename(), "utf8"), original);
    }
  });

  test("a timed-out poll cannot publish late results and polling resumes after it settles", async (t) => {
    const { state } = await setup(t);
    const original = await readFile(filename(), "utf8");
    state.hang = true;
    state.failKind = "permissions";
    t.mock.timers.tick(2_000);
    await until(() => Boolean(state.release));
    const count = state.calls.length;
    t.mock.timers.tick(5_000);
    await until(() => state.signals.at(-1).aborted);
    for (let i = 0; i < 20; i++) await immediate();
    t.mock.timers.tick(2_000);
    assert.equal(state.calls.length, count);
    state.release({ data: state.statuses });
    for (let i = 0; i < 20; i++) await immediate();
    assert.equal(await readFile(filename(), "utf8"), original);
    state.hang = false;
    state.failKind = undefined;
    await refresh(t, state);
  });

  for (const teardown of ["event", "dispose"]) {
    test(`${teardown} cancels an in-flight poll immediately and removes its file`, async (t) => {
      const { state, hooks, dispose } = await setup(t);
      state.hang = true;
      t.mock.timers.tick(2_000);
      await until(() => Boolean(state.release));
      const calls = state.calls.length;
      await (teardown === "dispose" ? hooks.dispose() : dispose());
      assert.ok(state.signals.at(-1).aborted);
      assert.ok(await absent(filename()));
      state.release({ data: state.statuses });
      for (let i = 0; i < 20; i++) await immediate();
      assert.ok(await absent(filename()));
      t.mock.timers.tick(10_000);
      assert.equal(state.calls.length, calls);
    });
  }

  test("dispose stops scheduled polling and shares idempotent cleanup with the legacy event", async (t) => {
    const { state, hooks, dispose, client } = await setup(t);
    const cleanup = hooks.dispose();
    assert.equal(hooks.dispose(), cleanup);
    await Promise.all([cleanup, dispose()]);
    assert.ok(await absent(filename()));
    const calls = state.calls.length;
    t.mock.timers.tick(10_000);
    assert.equal(state.calls.length, calls);

    const replacement = await plugin({ client, directory });
    t.after(() => replacement.dispose());
    await until(async () => !(await absent(filename())));
    await hooks.dispose();
    await dispose();
    assert.ok(!(await absent(filename())));
  });

  test("separate directory files and scoped disposal", async (t) => {
    const { hooks, client, dispose, state } = await setup(t);
    // An empty second instance avoids reusing the first instance's scoped mock.
    const empty = async () => ({ data: [] });
    const second = await plugin({ directory: "/other", client: {
      session: { ...client.session, status: async () => ({ data: {} }), list: empty },
      _client: { get: empty },
    } });
    t.after(() => second.event({ event: { type: "server.instance.disposed" } }));
    await until(async () => !(await absent(filename("/other"))));
    assert.equal((await snapshot("/other")).directory, "/other");
    await hooks.event({ event: { type: "server.instance.disposed", properties: { directory: "/other" } } });
    assert.ok(!(await absent(filename())));
    await dispose();
    assert.ok(await absent(filename()));
    assert.ok(!(await absent(filename("/other"))));
    const calls = state.calls.length;
    t.mock.timers.tick(10_000);
    assert.equal(state.calls.length, calls);
  });

  test("unavailable monitor filesystem never rejects plugin startup or disposal", async (t) => {
    await rm(join(homedir(), ".config"), { recursive: true, force: true });
    await writeFile(join(homedir(), ".config"), "blocked");
    t.after(() => rm(join(homedir(), ".config"), { force: true }));
    const empty = async () => ({ data: [] });
    const hooks = await plugin({ directory, client: {
      session: { status: async () => ({ data: {} }), list: empty }, _client: { get: empty },
    } });
    for (let i = 0; i < 100; i++) await immediate();
    await hooks.event({ event: { type: "server.instance.disposed" } });
    assert.equal(await readFile(join(homedir(), ".config"), "utf8"), "blocked");
  });
}
