import assert from "node:assert/strict";
import test from "node:test";
import { CONNECTION_FAILURES, failedConnectionResult, successfulConnectionResult } from "../agent/src/connection-test-contract.mjs";

test("connection result contract translates every expected mock outcome to safe Chinese UI text", () => {
  assert.deepEqual(successfulConnectionResult(true), { status: "SUCCESS", kind: "success", tool_calling_verified: true, message: "连接成功，模型响应正常，Tool Calling 已验证。" });
  for (const [input, kind] of [["401 unauthorized", "unauthorized"], ["404 model not found", "not_found"], ["429 rate limit", "rate_limited"], ["ETIMEDOUT", "timeout"], ["ENOTFOUND", "network"], ["invalid json response", "malformed"]]) {
    const result = failedConnectionResult(new Error(input));
    assert.equal(result.status, "ERROR");
    assert.equal(result.kind, kind);
    assert.equal(result.message, CONNECTION_FAILURES[kind]);
    assert.doesNotMatch(result.message, /stack|Error:|401|404|429/i);
  }
  const toolFailure = successfulConnectionResult(false);
  assert.equal(toolFailure.kind, "malformed");
  assert.equal(toolFailure.tool_calling_verified, false);
});
