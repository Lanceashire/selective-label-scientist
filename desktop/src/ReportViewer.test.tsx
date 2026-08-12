import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
const readReport = vi.hoisted(() => vi.fn().mockResolvedValue({ session_id:"s-report", path:"D:/reports/final_report.md", content:"# ECOMIC 中文科研报告\n\n## 研究问题\n比较预算策略\n\n## 实验与可见证据\n- Random" }));
vi.mock("./bridge", () => ({ DesktopBridge: { readReport, exportReport:vi.fn(), openReportLocation:vi.fn() } }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: vi.fn() }));
import { ReportViewer } from "./ReportViewer";
const session = { session_id:"s-report", status:"FINALIZED", schema:{row_count:1,column_count:1,sample_limit_for_llm:50,columns:{}}, candidates:{}, domain_spec:{} };
describe("ReportViewer", () => it("renders the generated Chinese Markdown report inside the GUI", async () => { render(<ReportViewer session={session} />); expect(await screen.findByRole("heading", { name:"ECOMIC 中文科研报告" })).toBeTruthy(); expect(screen.getByRole("heading", { name:"研究问题" })).toBeTruthy(); expect(screen.getByText("比较预算策略")).toBeTruthy(); expect(screen.getByText("Random")).toBeTruthy(); expect(readReport).toHaveBeenCalledWith("s-report"); }));
describe("ReportViewer failure recovery", () => it("shows a retryable error instead of permanent loading", async () => {
  readReport.mockRejectedValueOnce(new Error("report RPC failed"));
  render(<ReportViewer session={session} />);
  expect(await screen.findByText("报告加载失败")).toBeTruthy();
  expect(screen.getByText("report RPC failed")).toBeTruthy();
  expect(screen.getByRole("button", { name: "重新加载" })).toBeTruthy();
}));