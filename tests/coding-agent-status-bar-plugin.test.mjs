import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { setImmediate as immediate } from "node:timers/promises";
import test from "node:test";
import plugin from "../integrations/coding-agent-status-bar.js";

// Run all plugin code with an isolated HOME, never the user's monitor directory.
if (!process.env.MONITOR_PLUGIN_TEST_CHILD) {
  test("plugin suite in isolated HOME", async () => {
    const home = await mkdtemp(join(tmpdir(), "monitor-plugin-test-"));
    try {
      // Opt out of opening the real menu bar app; launching has its own tests.
      await mkdir(join(home, ".config", "coding-agent-status-bar"), { recursive: true });
      await writeFile(join(home, ".config", "coding-agent-status-bar", "no-autolaunch"), "");
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
  const parent = join(homedir(), ".config", "coding-agent-status-bar", "bridge");
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
  const settle = async () => { for (let i = 0; i < 30; i++) await immediate(); };

  // A controllable event stream; each subscribe() call opens a new one.
  function events() {
    const streams = [];
    const control = { down: false, attempts: 0 };
    const subscribe = ({ signal } = {}) => {
      control.attempts++;
      if (control.down) throw new Error("server unavailable");
      const stream = { queue: [], wake: undefined, error: undefined, ended: false, signal };
      streams.push(stream);
      return {
        async *[Symbol.asyncIterator]() {
          while (!signal?.aborted) {
            if (stream.queue.length) { yield stream.queue.shift(); continue; }
            if (stream.error) throw stream.error;
            if (stream.ended) return;
            await new Promise((resolve) => {
              stream.wake = resolve;
              signal?.addEventListener("abort", resolve, { once: true });
            });
          }
        },
      };
    };
    const current = () => streams.at(-1);
    return {
      streams, subscribe, control,
      push(...list) { current().queue.push(...list); current().wake?.(); },
      fail() { current().error = new Error("stream failed"); current().wake?.(); },
    };
  }

  async function setup(t, dir = directory, sessions = {}) {
    t.mock.timers.enable({ apis: ["Date", "setTimeout"], now: 1_000_000 });
    const stream = events();
    // pending: sessionID -> pending permission requests; unset means the list is unavailable.
    const state = { sessions, lookups: [], failLookup: false, pending: undefined, onList: undefined };
    const ctx = {
      location: { directory: dir, project: { id: "project", directory: dir, canonical: dir } },
      event: { subscribe: stream.subscribe },
      permission: {
        list: async ({ sessionID }) => {
          await state.onList?.();
          if (!state.pending) throw new Error("unavailable");
          return (state.pending[sessionID] ?? []).map((id) => ({ id, sessionID, action: "edit", resources: [] }));
        },
      },
      session: {
        get: async ({ sessionID }) => {
          state.lookups.push(sessionID);
          if (state.failLookup) throw new Error("lookup failed");
          const info = state.sessions[sessionID];
          if (!info) throw new Error("not found");
          return { id: sessionID, location: { directory: dir }, ...info };
        },
      },
    };
    const dispose = await plugin.setup(ctx);
    t.after(dispose);
    await until(async () => !(await absent(filename(dir))));
    await until(async () => (await readdir(parent)).every((name) => !name.endsWith(".tmp")));
    await settle();
    return { stream, state, dispose, ctx };
  }
  // Deliver events, then let the next 2-second snapshot pick them up.
  async function send(t, stream, ...list) {
    const before = (await snapshot()).updated;
    stream.push(...list);
    await settle();
    t.mock.timers.tick(2_000);
    await until(async () => (await snapshot()).updated > before);
    await settle();
  }
  // Move the clock forward and wait for the snapshot written at the new time.
  async function advance(t, ms) {
    t.mock.timers.tick(ms);
    await until(async () => (await snapshot()).updated === Date.now());
    await settle();
  }
  const event = (type, data, location = { directory }) => ({ id: "evt", created: 0, type, ...(location ? { location } : {}), data });
  const created = (id, extra = {}) => event("session.created",
    { sessionID: id, projectID: "project", location: { directory }, slug: "slug", version: "1", ...extra });

  test("a V2 plugin definition; exact sanitized contract and private atomic files", async (t) => {
    assert.deepEqual(Object.keys(await import("../integrations/coding-agent-status-bar.js")), ["default"]);
    assert.equal(plugin.id, "coding-agent-status-bar");
    assert.equal(typeof plugin.setup, "function");
    const { stream } = await setup(t);
    assert.deepEqual(await snapshot(), { version: 1, pid: process.pid, updated: Date.now(), directory, sessions: [] });
    await send(t, stream,
      created("active", { title: "Session", parentID: "parent", agent: "build", permissions: ["secret"] }),
      event("session.execution.started", { sessionID: "active" }),
      event("session.retry.scheduled", { sessionID: "active", assistantMessageID: "m", attempt: 1, at: 0,
        error: { message: "secret retry message" } }),
      event("form.created", { form: { id: "form", sessionID: "active", title: "secret prompt", fields: [] } }),
      event("permission.asked", { id: "perm", sessionID: "active", action: "bash", resources: ["secret arguments"] }),
    );
    assert.deepEqual(await snapshot(), {
      version: 1, pid: process.pid, updated: Date.now(), directory,
      sessions: [{ id: "active", title: "Session", directory, parentID: "parent", status: "retry",
        tools: [], question: true, permission: true }],
    });
    assert.equal((await stat(parent)).mode & 0o777, 0o700);
    assert.equal((await stat(filename())).mode & 0o777, 0o600);
    assert.equal((await readdir(parent)).length, 1);
  });

  test("tracks status, titles and pending requests through their lifecycle", async (t) => {
    const { stream } = await setup(t);
    await send(t, stream, created("s"), event("session.execution.started", { sessionID: "s" }));
    let [session] = (await snapshot()).sessions;
    assert.equal(session.title, "");
    assert.equal(session.status, "busy");
    await send(t, stream,
      event("session.renamed", { sessionID: "s", title: "Renamed" }),
      event("permission.asked", { id: "p1", sessionID: "s", action: "edit", resources: [] }),
      event("permission.asked", { id: "p2", sessionID: "s", action: "edit", resources: [] }),
      event("permission.replied", { sessionID: "s", requestID: "p1", reply: "once" }),
      event("form.created", { form: { id: "f", sessionID: "s", title: "q", fields: [] } }),
      event("form.replied", { id: "f", sessionID: "s", answer: {} }),
    );
    [session] = (await snapshot()).sessions;
    assert.deepEqual([session.title, session.question, session.permission], ["Renamed", false, true]);
    await send(t, stream,
      event("form.created", { form: { id: "g", sessionID: "s", title: "q", fields: [] } }),
      event("session.execution.interrupted", { sessionID: "s", reason: "user" }),
    );
    [session] = (await snapshot()).sessions;
    assert.deepEqual([session.status, session.question, session.permission], ["idle", false, false]);
    await send(t, stream, event("session.step.started", { sessionID: "s" }));
    assert.equal((await snapshot()).sessions[0].status, "busy");
    await send(t, stream, event("session.status", { sessionID: "s", status: { type: "idle" } }));
    assert.equal((await snapshot()).sessions[0].status, "idle");
    await send(t, stream, event("session.deleted", { sessionID: "s" }));
    assert.deepEqual((await snapshot()).sessions, []);
  });

  test("retains finished sessions for 60 seconds and looks them up again when they return", async (t) => {
    const { stream, state } = await setup(t, directory, { s: { title: "Looked up" } });
    await send(t, stream, created("s", { title: "Created" }), event("session.execution.succeeded", { sessionID: "s" }));
    assert.equal((await snapshot()).sessions[0].status, "idle");
    await advance(t, 58_000);
    assert.equal((await snapshot()).sessions.length, 1);
    await advance(t, 4_000);
    assert.equal((await snapshot()).sessions.length, 0);
    await send(t, stream, event("session.execution.started", { sessionID: "s" }));
    assert.deepEqual(state.lookups, ["s"]);
    assert.equal((await snapshot()).sessions[0].title, "Looked up");
  });

  test("pending requests keep a session listed however long they wait", async (t) => {
    const { stream } = await setup(t);
    await send(t, stream, created("s"), event("permission.asked", { id: "p", sessionID: "s", action: "x", resources: [] }));
    await advance(t, 30_000);
    await advance(t, 50_000);
    assert.equal((await snapshot()).sessions[0].permission, true);
    await send(t, stream, event("permission.replied", { sessionID: "s", requestID: "p", reply: "reject" }));
    await advance(t, 61_000);
    assert.deepEqual((await snapshot()).sessions, []);
  });

  test("permission flags are confirmed against OpenCode's pending list", async (t) => {
    const { stream, state } = await setup(t);
    await send(t, stream, created("s"),
      event("permission.asked", { id: "p1", sessionID: "s", action: "edit", resources: [] }),
      event("permission.asked", { id: "p2", sessionID: "s", action: "edit", resources: [] }));
    assert.equal((await snapshot()).sessions[0].permission, true);
    state.pending = { s: ["p2"] };
    await advance(t, 2_000);
    assert.equal((await snapshot()).sessions[0].permission, true);
    // A request asked while the check runs survives it.
    let release;
    state.pending = { s: [] };
    state.onList = () => new Promise((resolve) => { release = resolve; });
    t.mock.timers.tick(2_000);
    await until(() => Boolean(release));
    stream.push(event("permission.asked", { id: "p3", sessionID: "s", action: "edit", resources: [] }));
    await settle();
    release();
    await until(async () => (await snapshot()).updated === Date.now());
    assert.equal((await snapshot()).sessions[0].permission, true);
    state.onList = undefined;
    await advance(t, 2_000);
    assert.equal((await snapshot()).sessions[0].permission, false);
  });

  test("excludes other directories, resolving sessions whose events carry no location", async (t) => {
    const { stream, state, ctx } = await setup(t, directory, { mine: { title: "Mine", parentID: "root" } });
    const get = ctx.session.get;
    ctx.session.get = async (input) => input.sessionID === "theirs"
      ? { id: "theirs", title: "Theirs", location: { directory: "/other" } }
      : get(input);
    await send(t, stream,
      event("session.created", { sessionID: "foreign", projectID: "p", location: { directory: "/other" }, slug: "s", version: "1" }, { directory: "/other" }),
      event("session.execution.started", { sessionID: "foreign" }, null),
      event("session.execution.started", { sessionID: "elsewhere" }, { directory: "/other" }),
      event("session.execution.started", { sessionID: "theirs" }, null),
      event("session.execution.started", { sessionID: "theirs" }, null),
      event("session.execution.started", { sessionID: "mine" }, null),
    );
    assert.deepEqual((await snapshot()).sessions, [{ id: "mine", title: "Mine", directory, parentID: "root",
      status: "busy", tools: [], question: false, permission: false }]);
    assert.deepEqual(state.lookups, ["mine"]);
    await send(t, stream, event("session.moved", { sessionID: "mine", location: { directory: "/other" }, projectID: "p" }));
    assert.deepEqual((await snapshot()).sessions, []);
  });

  test("a failed lookup is retried, and events located here still count", async (t) => {
    const { stream, state } = await setup(t, directory, { s: { title: "Later" } });
    state.failLookup = true;
    await send(t, stream,
      event("session.execution.started", { sessionID: "nowhere" }, null),
      event("session.execution.started", { sessionID: "s" }),
    );
    assert.deepEqual((await snapshot()).sessions.map((s) => [s.id, s.title, s.status]), [["s", "", "busy"]]);
    state.failLookup = false;
    await send(t, stream, event("session.execution.started", { sessionID: "nowhere" }, null));
    assert.deepEqual(state.lookups, ["nowhere", "s", "nowhere"]);
  });

  test("a broken event stream stops refreshing the snapshot until it reconnects", async (t) => {
    const { stream } = await setup(t);
    await send(t, stream, created("s"), event("session.execution.started", { sessionID: "s" }));
    const original = await readFile(filename(), "utf8");
    stream.control.down = true;
    stream.fail();
    await settle();
    for (let i = 0; i < 5; i++) {
      t.mock.timers.tick(1_000);
      await settle();
    }
    assert.ok(stream.control.attempts >= 4);
    assert.equal(stream.streams.length, 1);
    assert.equal(await readFile(filename(), "utf8"), original);
    stream.control.down = false;
    t.mock.timers.tick(1_000);
    await until(() => stream.streams.length === 2);
    await settle();
    await send(t, stream, event("session.execution.succeeded", { sessionID: "s" }));
    assert.equal((await snapshot()).sessions[0].status, "idle");
  });

  test("cleanup stops the stream and snapshots, removes the file, and is idempotent", async (t) => {
    const { stream, dispose } = await setup(t);
    const first = dispose();
    assert.equal(dispose(), first);
    await first;
    assert.ok(await absent(filename()));
    assert.ok(stream.streams[0].signal.aborted);
    t.mock.timers.tick(10_000);
    await settle();
    assert.ok(await absent(filename()));
    assert.equal(stream.streams.length, 1);
  });

  test("separate directory files and scoped cleanup", async (t) => {
    const { dispose } = await setup(t);
    const other = events();
    const second = await plugin.setup({ location: { directory: "/other" }, event: { subscribe: other.subscribe },
      session: { get: async () => { throw new Error("unused"); } } });
    t.after(second);
    await until(async () => !(await absent(filename("/other"))));
    assert.equal((await snapshot("/other")).directory, "/other");
    await second();
    assert.ok(!(await absent(filename())));
    assert.ok(await absent(filename("/other")));
    await dispose();
    assert.ok(await absent(filename()));
  });

  test("unavailable monitor filesystem never rejects plugin startup or cleanup", async (t) => {
    await rm(join(homedir(), ".config"), { recursive: true, force: true });
    await writeFile(join(homedir(), ".config"), "blocked");
    t.after(() => rm(join(homedir(), ".config"), { force: true }));
    const dispose = await plugin.setup({ location: { directory }, event: events(), session: {} });
    await settle();
    await dispose();
    assert.equal(await readFile(join(homedir(), ".config"), "utf8"), "blocked");
  });
}
