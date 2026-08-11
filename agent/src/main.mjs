import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { hydrateCredentialToProcess, loadNonSecretConfig } from "./settings.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const valueAfter = (flag) => { const index = args.indexOf(flag); return index >= 0 ? args[index + 1] : undefined; };
function runHeadlessImport() {
  const data = valueAfter("--data");
  if (!data) { console.error("Headless mode requires --data. Run 'npm run ecomic' to start the interactive Pi workbench."); process.exitCode = 2; return; }
  const child = spawn(process.env.ECOMIC_PYTHON || "python", ["-m", "agent_backend.cli", "--data", data, "--description", valueAfter("--description") || ""], { cwd: root, stdio: "inherit", windowsHide: true });
  child.on("error", (error) => { console.error(`Python backend failed to start: ${error.message}`); process.exitCode = 1; });
  child.on("exit", (code) => { process.exitCode = code ?? 1; });
}
if (args.includes("--headless")) runHeadlessImport();
else {
  // Pi resolves its initial model before extensions receive session_start. Restore the
  // locally saved credential first so its own provider registry authenticates at boot.
  const savedConfig = loadNonSecretConfig();
  if (savedConfig.provider) hydrateCredentialToProcess(savedConfig.provider);
  const cli = path.join(root, "vendor", "pi", "packages", "coding-agent", "dist", "cli.js");
  const extension = (name) => path.join(root, "agent", "src", name);
  const child = spawn(process.execPath, [cli, "--extension", extension("pi-extension.ts"), "--extension", extension("ecomic-api-runtime.ts"), "--extension", extension("ecomic-research-loop-tools.ts"), "--extension", extension("ecomic-workbench.ts"), "--extension", extension("ecomic-history.ts"), ...args], { cwd: root, stdio: "inherit", windowsHide: true });
  child.on("error", (error) => { console.error(`ECOMIC Pi workbench failed to start: ${error.message}`); process.exitCode = 1; });
  child.on("exit", (code) => { process.exitCode = code ?? 1; });
}
