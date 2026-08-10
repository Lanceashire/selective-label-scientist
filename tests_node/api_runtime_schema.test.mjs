import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

test("API runtime uses Pi registry, a bounded tool probe, and no direct business fetch", () => {
  const source = fs.readFileSync("agent/src/ecomic-api-runtime.ts", "utf8");
  assert.match(source, /pi\.registerProvider/);
  assert.match(source, /ctx\.modelRegistry\.complete/);
  assert.match(source, /ecomic_connection_probe/);
  assert.match(source, /tool_calling_verified/);
  assert.match(source, /maxTokens:\s*32/);
  assert.doesNotMatch(source, /\bfetch\s*\(/);
  assert.doesNotMatch(source, /Authorization:\s*Bearer/);
});
