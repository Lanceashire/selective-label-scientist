import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ startScientist: vi.fn(), cancelScientist: vi.fn(), subscribeScientistEvents: vi.fn() }));
vi.mock("./bridge", () => ({ DesktopBridge: mocks }));
import { ScientistControl } from "./ScientistControl";

const session = { session_id: "session-agent-ui", status: "RESEARCH", domain_spec: {}, candidates: {}, schema: { row_count: 4, column_count: 1, sample_limit_for_llm: 50, columns: {} } };

beforeEach(() => { mocks.startScientist.mockReset(); mocks.cancelScientist.mockReset(); mocks.subscribeScientistEvents.mockReset(); });

describe("Scientist control", () => {
  it("starts a task immediately through DesktopBridge without waiting for Agent completion", async () => {
    mocks.subscribeScientistEvents.mockResolvedValue(() => undefined);
    mocks.startScientist.mockResolvedValue({ task_id: "task_ui_1", status: "STARTING", session_id: session.session_id });
    render(<ScientistControl session={session} />);
    fireEvent.change(screen.getByLabelText("科研问题"), { target: { value: "比较两种策略" } });
    fireEvent.click(screen.getByRole("button", { name: "启动 Pi Scientist Agent" }));
    await waitFor(() => expect(mocks.startScientist).toHaveBeenCalledWith("session-agent-ui", "比较两种策略"));
    expect(screen.getByRole("status").textContent).toContain("task_ui_1");
    expect(screen.getByText(/状态：STARTING/)).toBeTruthy();
  });

  it("renders incoming Agent events without waiting for a final invoke response", async () => {
    let handler: ((event: { type: "tool_start"; session_id: string; tool: string }) => void) | undefined;
    mocks.subscribeScientistEvents.mockImplementation(async (next) => { handler = next; return () => undefined; });
    render(<ScientistControl session={session} />);
    await waitFor(() => expect(mocks.subscribeScientistEvents).toHaveBeenCalled());
    await act(async () => { handler?.({ type: "tool_start", session_id: session.session_id, tool: "run_experiment" }); });
    const stream = await screen.findByLabelText("实时科研事件");
    expect(stream.textContent).toContain("正在执行：run_experiment");
  });

  it("cancels an active task by task_id and keeps the Session recoverable", async () => {
    mocks.subscribeScientistEvents.mockResolvedValue(() => undefined);
    mocks.startScientist.mockResolvedValue({ task_id: "task_cancel_1", status: "STARTING", session_id: session.session_id });
    mocks.cancelScientist.mockResolvedValue({ task_id: "task_cancel_1", status: "CANCELLED", session_id: session.session_id });
    render(<ScientistControl session={session} />);
    fireEvent.click(screen.getByRole("button", { name: "启动 Pi Scientist Agent" }));
    expect(await screen.findByRole("button", { name: "停止研究" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "停止研究" }));
    await waitFor(() => expect(mocks.cancelScientist).toHaveBeenCalledWith("task_cancel_1"));
    expect(screen.getByRole("status").textContent).toContain("Session 已保留");
    expect(screen.getByText(/状态：CANCELLED/)).toBeTruthy();
  });
});