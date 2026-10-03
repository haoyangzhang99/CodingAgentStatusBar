import { spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, chmod, writeFile, rename, unlink } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

const BUNDLE_ID = "io.github.haoyangzhang99.OpenCodeStatusBar";
// Shared across plugin module instances, so each OpenCode process launches once.
const LAUNCHED = Symbol.for("opencode-status-bar.launched");
const INTERVAL = 2_000;
const RETENTION = 60_000;
const RESUBSCRIBE = 1_000;

// Open the menu bar app when OpenCode starts. OpenCode loads this plugin once per
// project, so only the first load in a process does anything. Never throws.
function launchStatusBar() {
  try {
    if (globalThis[LAUNCHED] || process.platform !== "darwin") return;
    globalThis[LAUNCHED] = true;
    const home = homedir();
    if (existsSync(join(home, ".config", "opencode-status-bar", "no-autolaunch"))) return;
    const open = (args, fallback) => {
      const child = spawn("/usr/bin/open", args, { stdio: "ignore", detached: true });
      child.on("error", () => {});
      if (fallback) child.on("exit", (code) => { if (code !== 0) fallback(); });
      child.unref();
    };
    // -g opens it without stealing focus; an already-running app is left as is.
    // Fall back to the install path if macOS hasn't indexed the app's ID yet.
    open(["-g", "-b", BUNDLE_ID], () => {
      try { open(["-g", join(home, "Applications", "OpenCode Status Bar.app")]); } catch {}
    });
  } catch {
    // Launching is a convenience; it must never break OpenCode.
  }
}

const ENDED = new Set(["session.execution.succeeded", "session.execution.failed", "session.execution.interrupted"]);

// OpenCode 2 plugin: a default export with an id and setup(ctx).
export default {
  id: "opencode-status-bar",
  setup: statusBarBridge,
};

// The V2 plugin context cannot list sessions, their status or pending questions, so the
// bridge follows the event stream and keeps its own view of this directory's sessions.
function statusBarBridge(ctx) {
  launchStatusBar();
  const directory = ctx.location.directory;
  const parent = join(homedir(), ".config", "opencode-status-bar", "bridge");
  const hash = createHash("sha256").update(directory).digest("hex");
  const filename = join(parent, `${process.pid}-${hash}.json`);
  const controller = new AbortController();
  const signal = controller.signal;
  // id -> { title, parentID?, status, questions, permissions, lastActive }
  const sessions = new Map();
  // id -> Promise resolving to true (this directory), false (elsewhere) or undefined (unknown yet).
  const owners = new Map();
  let connected = false;
  let disposed = false;
  let timer;
  let writing;
  let cleanup;

  function track(id, info) {
    let session = sessions.get(id);
    if (!session) {
      session = { title: "", status: "idle", questions: new Set(), permissions: new Set(), lastActive: Date.now() };
      sessions.set(id, session);
    }
    if (typeof info?.title === "string") session.title = info.title;
    if (typeof info?.parentID === "string") session.parentID = info.parentID;
    return session;
  }

  function forget(id) {
    sessions.delete(id);
    owners.set(id, Promise.resolve(false));
  }

  // Look a session up once to learn its directory and title. A failed lookup is retried
  // on the session's next event.
  function owned(id, location) {
    if (location && typeof location.directory === "string") {
      if (location.directory !== directory) return Promise.resolve(false);
      if (sessions.has(id)) return Promise.resolve(true);
    }
    if (!owners.has(id)) {
      owners.set(id, (async () => {
        const info = await ctx.session.get({ sessionID: id }, { signal });
        if (info?.id !== id || typeof info.location?.directory !== "string") throw new Error("Invalid session");
        if (info.location.directory !== directory) {
          sessions.delete(id);
          return false;
        }
        if (!disposed) track(id, info);
        return true;
      })().catch(() => {
        owners.delete(id);
        return location?.directory === directory ? (track(id), true) : undefined;
      }));
    }
    return owners.get(id);
  }

  async function handle(event) {
    const data = event?.data;
    if (!data || typeof data !== "object") return;
    const id = event.type === "form.created" ? data.form?.sessionID : data.sessionID;
    if (typeof id !== "string") return;
    if (event.type === "session.deleted") return forget(id);
    if (event.type === "session.created") {
      if (data.location?.directory !== directory) return forget(id);
      owners.set(id, Promise.resolve(true));
      return void track(id, data);
    }
    let location = event.location;
    if (event.type === "session.moved") {
      if (data.location?.directory !== directory) return forget(id);
      owners.delete(id);
      location = undefined;
    }
    if (await owned(id, location) !== true || disposed) return;
    const session = track(id);
    session.lastActive = Date.now();
    switch (event.type) {
      case "session.renamed":
        if (typeof data.title === "string") session.title = data.title;
        break;
      case "session.execution.started":
      case "session.step.started":
        session.status = "busy";
        break;
      case "session.retry.scheduled":
        session.status = "retry";
        break;
      case "session.status":
        if (["busy", "idle", "retry"].includes(data.status?.type)) session.status = data.status.type;
        break;
      case "session.idle":
        session.status = "idle";
        break;
      case "permission.asked":
        if (typeof data.id === "string") session.permissions.add(data.id);
        break;
      case "permission.replied":
        session.permissions.delete(data.requestID);
        break;
      case "form.created":
        if (typeof data.form.id === "string") session.questions.add(data.form.id);
        break;
      case "form.replied":
      case "form.cancelled":
        session.questions.delete(data.id);
        break;
    }
    // A finished run can't still be waiting for an answer.
    if (ENDED.has(event.type)) {
      session.status = "idle";
      session.questions.clear();
      session.permissions.clear();
    }
  }

  async function listen() {
    while (!disposed) {
      try {
        const stream = ctx.event.subscribe({ signal });
        connected = true;
        for await (const event of stream) {
          if (disposed) return;
          try { await handle(event); } catch {}
        }
      } catch {
        // Fall through and resubscribe.
      }
      // While disconnected the snapshot is not refreshed, so the app treats it as offline.
      connected = false;
      if (disposed) return;
      await new Promise((resolve) => {
        const wait = setTimeout(resolve, RESUBSCRIBE);
        wait.unref?.();
        signal.addEventListener("abort", () => { clearTimeout(wait); resolve(); }, { once: true });
      });
    }
  }

  function snapshot() {
    const now = Date.now();
    const list = [];
    for (const [id, session] of sessions) {
      const pending = session.questions.size > 0 || session.permissions.size > 0;
      if (pending || session.status !== "idle") session.lastActive = now;
      if (session.lastActive < now - RETENTION) {
        // Look it up again if it comes back, so it gets its title.
        sessions.delete(id);
        owners.delete(id);
        continue;
      }
      list.push({
        id, title: session.title, directory,
        ...(session.parentID === undefined ? {} : { parentID: session.parentID }),
        status: session.status, tools: [],
        question: session.questions.size > 0, permission: session.permissions.size > 0,
      });
    }
    return { version: 1, pid: process.pid, updated: now, directory, sessions: list };
  }

  // Not every resolved request emits permission.replied, so confirm flagged sessions against
  // OpenCode's pending list. Keep the flag if the check fails.
  async function reconcile() {
    await Promise.all([...sessions].filter(([, session]) => session.permissions.size > 0).map(async ([id, session]) => {
      const known = [...session.permissions];
      try {
        const pending = await ctx.permission.list({ sessionID: id }, { signal });
        if (!Array.isArray(pending)) return;
        const ids = new Set(pending.map((request) => request?.id));
        // Only drop requests known before the check; newer ones may not be listed yet.
        for (const request of known) if (!ids.has(request)) session.permissions.delete(request);
      } catch {}
    }));
  }

  async function write() {
    let temporary;
    try {
      if (disposed || !connected) return;
      await reconcile();
      if (disposed || !connected) return;
      const data = JSON.stringify(snapshot());
      await mkdir(parent, { recursive: true, mode: 0o700 });
      await chmod(parent, 0o700);
      temporary = `${filename}.${randomUUID()}.tmp`;
      await writeFile(temporary, data, { mode: 0o600, flag: "wx" });
      if (disposed) return;
      await rename(temporary, filename);
      temporary = undefined;
    } catch {
      // Never disrupt OpenCode; the app treats a stale snapshot as offline.
    } finally {
      if (temporary) await unlink(temporary).catch(() => {});
    }
  }

  function tick() {
    writing = write().finally(() => {
      if (disposed) return;
      timer = setTimeout(tick, INTERVAL);
      timer.unref?.();
    });
  }

  void listen();
  tick();

  return function dispose() {
    if (!cleanup) {
      disposed = true;
      connected = false;
      clearTimeout(timer);
      controller.abort();
      cleanup = (async () => {
        await writing;
        await unlink(filename).catch(() => {});
      })();
    }
    return cleanup;
  };
}
