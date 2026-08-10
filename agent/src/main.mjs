import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const valueAfter = (flag) => { const i = args.indexOf(flag); return i >= 0 ? args[i + 1] : undefined; };
const data = valueAfter("--data");
const description = valueAfter("--description") || "";
const budget = valueAfter("--budget");
const seed = valueAfter("--seed");
const pyArgs = ["-m", "agent_backend.cli", "--root", root];
const flags = [["--data", data], ["--description", description], ["--budget", budget], ["--seed", seed], ["--id", valueAfter("--id")], ["--decision", valueAfter("--decision")], ["--target", valueAfter("--target")], ["--cost", valueAfter("--cost")]];
for (const [flag, value] of flags) if (value) pyArgs.push(flag, value);

console.log("╔════════════════════════ ECOMIC ════════════════════════╗");
console.log("║              跨领域选择性标签科研智能体               ║");
console.log("╠═════════════════════════════════════════════════════════╣");
console.log(`║ 运行模式：${process.env.ECOMIC_LLM_PROVIDER || "mock"}（LLM 可选，数值工具由 Python 执行）`);
console.log(`║ 数据集：${data ? path.resolve(data) : "等待输入"}`);
console.log("╚═════════════════════════════════════════════════════════╝");
if (!data) process.stdout.write("请输入数据集路径（CSV/Parquet）：");
const child = spawn(process.env.ECOMIC_PYTHON || "python", pyArgs, { cwd: root, stdio: "inherit", windowsHide: true });
child.on("error", (error) => { console.error(`启动 Python 后端失败：${error.message}`); process.exitCode = 1; });
child.on("exit", (code) => { process.exitCode = code ?? 1; });
