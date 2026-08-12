import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ open: vi.fn(), inspectDataset: vi.fn(), loadDataset: vi.fn(), restartBackend: vi.fn(), subscribePrecheckEvents: vi.fn() }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: mocks.open }));
vi.mock("./bridge", () => ({ DesktopBridge: { inspectDataset: mocks.inspectDataset, loadDataset: mocks.loadDataset, restartBackend: mocks.restartBackend, subscribePrecheckEvents: mocks.subscribePrecheckEvents } }));
import { DatasetImportPage } from "./DatasetImportPage";

describe("Dataset import page", () => {
  it("does nothing when the native file chooser is cancelled", async () => {
    mocks.open.mockResolvedValue(null);
    render(<DatasetImportPage />);
    fireEvent.click(screen.getByRole("button", { name: "选择文件" }));
    await waitFor(() => expect(mocks.open).toHaveBeenCalled());
    expect((screen.getByLabelText("数据集路径") as HTMLInputElement).value).toBe("");
    expect(mocks.inspectDataset).not.toHaveBeenCalled();
  });

  it("accepts a native drag-and-drop path and asks the bridge only for a bounded preview", async () => {
    mocks.inspectDataset.mockResolvedValue({ path: "D:\\data\\study.csv", sha256: "abc", format: "csv", size_bytes: 123, schema: { row_count: 3, column_count: 1, sample_limit_for_llm: 50, columns: { decision: { dtype: "VARCHAR", missing_count: 0, missing_rate: 0, unique_count: 2, top_values: { yes: 2 } } } }, sample: [{ decision: "yes" }] });
    render(<DatasetImportPage />);
    const file = new File(["id,decision\n1,yes"], "study.csv", { type: "text/csv" }) as File & { path?: string };
    Object.defineProperty(file, "path", { value: "D:\\data\\study.csv" });
    fireEvent.drop(screen.getByRole("button", { name: "拖拽数据集到这里" }), { dataTransfer: { files: { item: () => file } } });
    expect((screen.getByLabelText("数据集路径") as HTMLInputElement).value).toBe("D:\\data\\study.csv");
    fireEvent.click(screen.getByRole("button", { name: "预检数据集" }));
    await waitFor(() => expect(mocks.inspectDataset).toHaveBeenCalledWith("D:\\data\\study.csv"));
    expect(screen.getByText("abc")).toBeTruthy();
    expect(screen.getByText("3 / 1")).toBeTruthy();
  });
  it("cancels an in-flight precheck by restarting only the local backend", async () => {
    mocks.inspectDataset.mockImplementation(() => new Promise(() => undefined));
    mocks.restartBackend.mockResolvedValue({ status: "RESTARTED" });
    render(<DatasetImportPage />);
    fireEvent.change(screen.getByLabelText("数据集路径"), { target: { value: "D:\\data\\slow.csv" } });
    fireEvent.click(screen.getByRole("button", { name: "预检数据集" }));
    expect(await screen.findByRole("button", { name: "取消预检" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "取消预检" }));
    await waitFor(() => expect(mocks.restartBackend).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("status").textContent).toContain("预检已取消");
  });
  it("renders streamed precheck stage and percentage without waiting for completion", async () => {
    let handler: ((event: { type: "precheck_progress"; request_id: string; stage: "读取文件" | "解析 Schema" | "统计字段" | "生成样本" | "完成"; percent: number }) => void) | undefined;
    mocks.subscribePrecheckEvents.mockImplementation(async (next: typeof handler) => { handler = next; return () => undefined; });
    mocks.inspectDataset.mockImplementation(() => new Promise(() => undefined));
    render(<DatasetImportPage />);
    fireEvent.change(screen.getByLabelText("数据集路径"), { target: { value: "D:\\data\\progress.csv" } });
    fireEvent.click(screen.getByRole("button", { name: "预检数据集" }));
    await waitFor(() => expect(handler).toBeTruthy());
    handler?.({ type: "precheck_progress", request_id: "req_1", stage: "统计字段", percent: 82 });
    expect(await screen.findByText("预检阶段：统计字段 · 82%")).toBeTruthy();
  });
});
