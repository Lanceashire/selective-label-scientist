import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ startScientist: vi.fn(), subscribeScientistEvents: vi.fn() }));
vi.mock("./bridge", () => ({ DesktopBridge: mocks }));
import { ScientistControl } from "./ScientistControl";

const session = { session_id: "session-agent-ui", status: "RESEARCH", domain_spec: {}, candidates: {}, schema: { row_count: 4, column_count: 1, sample_limit_for_llm: 50, columns: {} } };

describe("Scientist control", () => {
  it("submits the current session and research question only through DesktopBridge", async () => {
    mocks.subscribeScientistEvents.mockResolvedValue(() => undefined);
    mocks.startScientist.mockResolvedValue({ status: "COMPLETED", session_id: session.session_id, events: [{ type: "tool_end", tool: "observe_state" }, { type: "tool_end", tool: "audit_environment" }] });
    render(<ScientistControl session={session} />);
    fireEvent.change(screen.getByLabelText("科研问题"), { target: { value: "比较两种策略" } });
    fireEvent.click(screen.getByRole("button", { name: "启动 Pi Scientist Agent" }));
    await waitFor(() => expect(mocks.startScientist).toHaveBeenCalledWith("session-agent-ui", "比较两种策略"));
    expect(screen.getByRole("status").textContent).toContain("observe_state");
  });

  it("renders incoming Agent events without waiting for the final invoke response", async () => {
    let handler: ((event: { type: "tool_start"; session_id: string; tool: string }) => void) | undefined;
    mocks.subscribeScientistEvents.mockImplementation(async (next) => { handler = next; return () => undefined; });
    render(<ScientistControl session={session} />);
    await waitFor(() => expect(mocks.subscribeScientistEvents).toHaveBeenCalled());
    await act(async () => { handler?.({ type: "tool_start", session_id: session.session_id, tool: "run_experiment" }); });
    const stream = await screen.findByLabelText("实时科研事件");
    expect(stream.textContent).toContain("正在执行：run_experiment");
  });

  it("shows recovery after an Agent host interruption and retries the same session", async () => {
    let handler: ((event: { type: "agent_error"; session_id: string }) => void) | undefined;
    mocks.subscribeScientistEvents.mockImplementation(async (next) => { handler = next; return () => undefined; });
    mocks.startScientist.mockResolvedValue({ status: "COMPLETED", session_id: session.session_id, events: [] });
    render(<ScientistControl session={session} />);
    await waitFor(() => expect(mocks.subscribeScientistEvents).toHaveBeenCalled());
    await act(async () => { handler?.({ type: "agent_error", session_id: session.session_id }); });
    expect(screen.getByRole("status").textContent).toContain("Agent 后台已停止");
    fireEvent.click(screen.getByRole("button", { name: "重新连接并恢复研究" }));
    await waitFor(() => expect(mocks.startScientist).toHaveBeenCalledWith("session-agent-ui", expect.any(String)));
  });
});