import { createHash, randomUUID } from "node:crypto";
import { mkdir, chmod, writeFile, rename, unlink } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

// Only the default export is a plugin: OpenCode invokes every exported function.
export default async function statusBarBridge({ client, directory }) {
  const interval = 2_000;
  const timeout = 5_000;
  const retention = 60_000;
  const parent = join(homedir(), ".config", "opencode-status-bar", "bridge");
  const hash = createHash("sha256").update(directory).digest("hex");
  const filename = join(parent, `${process.pid}-${hash}.json`);
  let recent = new Map();
  let disposed = false;
  let blocked = false;
  let timer;
  let controller;
  let inFlight;
  let cleanup;

  async function poll() {
    if (disposed) return;
    let temporary;
    let deadline;
    try {
      // If a transport ignores cancellation, do not stack requests behind it.
      if (blocked) return;
      blocked = true;
      controller = new AbortController();
      const signal = controller.signal;
      const options = { query: { directory }, signal, throwOnError: true };
      const expires = new Promise((_, reject) => {
        signal.addEventListener("abort", () => reject(new Error("Poll cancelled")), { once: true });
        deadline = setTimeout(() => controller.abort(), timeout);
        deadline.unref?.();
      });
      const started = Date.now();
      const nextRecent = new Map(recent);
      const data = async (request) => {
        const result = await request;
        if (!result || result.error || result.data === undefined) throw new Error("Invalid response");
        return result.data;
      };
      const work = (async () => {
        // The injected desktop v1 SDK has no question/permission namespace.
        // Its underlying client retains both auth and the in-process fetch.
        const results = await Promise.allSettled([
          () => client.session.status(options),
          () => client._client.get({ ...options, url: "/question" }),
          () => client._client.get({ ...options, url: "/permission" }),
          () => client.session.list({ ...options, query: { directory, start: started - retention } }),
        ].map((request) => data(Promise.resolve().then(request))));
        const [statuses, questions, permissions, listed] = results.map((result) => {
          if (result.status === "rejected") throw result.reason;
          return result.value;
        });
        if (!statuses || typeof statuses !== "object" || Array.isArray(statuses) ||
            !Array.isArray(questions) || !Array.isArray(permissions) || !Array.isArray(listed)) {
          throw new Error("Invalid poll data");
        }
        const pending = (requests) => new Set(requests.map((request) => {
          if (typeof request?.sessionID !== "string") throw new Error("Invalid pending request");
          return request.sessionID;
        }));
        const question = pending(questions);
        const permission = pending(permissions);
        const details = new Map(listed.map((session) => [session.id, session]));
        for (const [id, status] of Object.entries(statuses)) {
          if (!["busy", "idle", "retry"].includes(status?.type)) throw new Error("Invalid status");
          if (status.type !== "idle") nextRecent.set(id, started);
        }
        for (const id of [...question, ...permission]) nextRecent.set(id, started);
        for (const session of listed) {
          if (session.directory === directory && Number.isFinite(session.time?.updated) &&
              session.time.updated >= started - retention) {
            nextRecent.set(session.id, Math.max(nextRecent.get(session.id) ?? 0,
              Math.min(started, session.time.updated)));
          }
        }
        const sessions = [];
        for (const [id, lastActive] of nextRecent) {
          if (lastActive < started - retention) {
            nextRecent.delete(id);
            continue;
          }
          if (signal.aborted) throw new Error("Poll cancelled");
          const session = details.get(id) ?? await data(client.session.get({ ...options, path: { id } }));
          if (session.id !== id || typeof session.title !== "string" || typeof session.directory !== "string" ||
              (session.parentID !== undefined && typeof session.parentID !== "string")) {
            throw new Error("Invalid session");
          }
          if (session.directory !== directory) {
            nextRecent.delete(id);
            continue;
          }
          sessions.push({
            id, title: session.title, directory: session.directory,
            ...(session.parentID === undefined ? {} : { parentID: session.parentID }),
            status: statuses[id]?.type ?? "idle", tools: [],
            question: question.has(id), permission: permission.has(id),
          });
        }
        return { version: 1, pid: process.pid, updated: started, directory, sessions };
      })();
      // Wait for all transport requests, even after the deadline, before retrying.
      work.then(() => { blocked = false; }, () => { blocked = false; });
      const snapshot = await Promise.race([work, expires]);
      if (disposed || signal.aborted) return;
      await mkdir(parent, { recursive: true, mode: 0o700 });
      await chmod(parent, 0o700);
      temporary = `${filename}.${randomUUID()}.tmp`;
      await writeFile(temporary, JSON.stringify(snapshot), { mode: 0o600, flag: "wx" });
      if (disposed || signal.aborted) return;
      await rename(temporary, filename);
      recent = nextRecent;
    } catch {
      // Leave the last successful timestamp untouched; never disrupt OpenCode.
      controller?.abort();
    } finally {
      clearTimeout(deadline);
      if (temporary) await unlink(temporary).catch(() => {});
      if (!disposed) {
        timer = setTimeout(() => { inFlight = poll(); }, interval);
        timer.unref?.();
      }
    }
  }

  function dispose() {
    if (!cleanup) {
      disposed = true;
      clearTimeout(timer);
      controller?.abort();
      // Both teardown paths may run; never unlink a replacement context's file twice.
      cleanup = (async () => {
        await inFlight;
        await unlink(filename).catch(() => {});
      })();
    }
    return cleanup;
  }

  inFlight = poll();
  return {
    dispose,
    async event({ event }) {
      if (event.type !== "server.instance.disposed" ||
          (event.properties?.directory !== undefined && event.properties.directory !== directory)) return;
      await dispose();
    },
  };
}
