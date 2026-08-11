import assert from "node:assert/strict";
import { once } from "node:events";
import http from "node:http";
import { spawn } from "node:child_process";
import test from "node:test";

function runProbe(environment) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["agent/src/pi-connection-probe.mjs"], { cwd: process.cwd(), env: { ...process.env, ...environment }, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? resolve({ stdout, stderr }) : reject(new Error(`probe exit ${code}: ${stderr}`)));
  });
}

test("Pi connection probe performs a minimum custom OpenAI-Compatible tool-call request and keeps its key out of output", async () => {
  const fakeKey = "test-probe-key-9876";
  let requestBody = "";
  let authorization = "";
  const server = http.createServer(async (request, response) => {
    for await (const chunk of request) requestBody += chunk;
    authorization = String(request.headers.authorization ?? "");
    response.writeHead(200, { "content-type": "text/event-stream" });
    response.write(`data: ${JSON.stringify({ id: "probe", choices: [{ delta: { tool_calls: [{ index: 0, id: "call_probe", type: "function", function: { name: "ecomic_connection_probe", arguments: "{\\\"ok\\\":true}" } }] }, finish_reason: null }] })}\n\n`);
    response.write(`data: ${JSON.stringify({ id: "probe", choices: [{ delta: {}, finish_reason: "tool_calls" }] })}\n\n`);
    response.end("data: [DONE]\n\n");
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const { port } = server.address();
  try {
    const { stdout, stderr } = await runProbe({ ECOMIC_PROVIDER: "custom_openai_compatible", ECOMIC_MODEL: "probe-model", ECOMIC_BASE_URL: `http://127.0.0.1:${port}/v1`, ECOMIC_CUSTOM_API_KEY: fakeKey });
    const result = JSON.parse(stdout);
    assert.equal(result.status, "SUCCESS");
    assert.equal(result.tool_calling_verified, true);
    assert.match(requestBody, /ecomic_connection_probe/);
    assert.equal(authorization, `Bearer ${fakeKey}`);
    assert.doesNotMatch(stdout, new RegExp(fakeKey));
    assert.equal(stderr, "");
  } finally { server.close(); }
});
