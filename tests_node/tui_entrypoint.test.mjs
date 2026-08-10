import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("default launcher starts Pi TUI and headless import remains explicit", () => {
  const source = fs.readFileSync("agent/src/main.mjs", "utf8");
  assert.match(source, /args\.includes\("--headless"\)/);
  assert.match(source, /"coding-agent", "dist", "cli\.js"/);
  assert.match(source, /ecomic-api-runtime\.ts/);
  assert.match(source, /ecomic-workbench\.ts/);
  assert.match(source, /ecomic-history\.ts/);
});

test("history restoration and Agent path use the same global active-session contract", () => {
  const workbench = fs.readFileSync("agent/src/ecomic-workbench.ts", "utf8");
  const history = fs.readFileSync("agent/src/ecomic-history.ts", "utf8");
  const runtime = fs.readFileSync("agent/src/ecomic-api-runtime.ts", "utf8");
  assert.match(workbench, /Symbol\.for\("ecomic\.active-session-id"\)/);
  assert.match(history, /setActiveSession\(sessionId\)/);
  assert.match(runtime, /getActiveSession\(\)/);
});
