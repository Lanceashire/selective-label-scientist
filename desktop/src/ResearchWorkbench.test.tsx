import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ getSession: vi.fn(), subscribeScientistEvents: vi.fn() }));
vi.mock("./bridge", () => ({ DesktopBridge: { subscribeScientistEvents: mocks.subscribeScientistEvents, getSession: mocks.getSession } }));
vi.mock("./ScientistControl", () => ({ ScientistControl: () => <div>Agent 输入区</div> }));
import { ResearchWorkbench } from "./ResearchWorkbench";

const session = { session_id:"session-workbench", status:"RESEARCH", candidates:{}, schema:{row_count:120,column_count:6,sample_limit_for_llm:50,columns:{}}, domain_spec:{domain_name:"selective labels",historical_decision:{column:"decision",observed_action_values:["reviewed"]},outcome:{column:"outcome"},observation_cost:{column:"cost"}} };
const snapshot = { session_id:"session-workbench", status:"RESEARCH", research_plan_locked:false, final_evaluation_revealed:false, hypotheses:[{hypothesis_id:"h1",content:"test hypothesis",status:"ACTIVE",version:1}], plans:[{plan_id:"p1",recipe_json:"{}"}], runs:[{run_id:"r1",policy:"Random",budget:10,status:"COMPLETED",round_end:2}] };

afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); });

describe("ResearchWorkbench", () => {
  it("shows persisted session evidence with data environment and Oracle isolation in one page", async () => {
    mocks.getSession.mockResolvedValue(snapshot);
    mocks.subscribeScientistEvents.mockResolvedValue(() => undefined);
    render(<ResearchWorkbench session={session} />);
    expect(await screen.findByText("test hypothesis")).toBeTruthy();
    expect(screen.getByText("数据环境")).toBeTruthy();
    expect(screen.getByText("研究时间线")).toBeTruthy();
    expect(screen.getByText("当前证据")).toBeTruthy();
    expect(screen.getByText(/Oracle LOCKED/)).toBeTruthy();
    expect(screen.getByText("Agent 输入区")).toBeTruthy();
  });

  it("coalesces a 1000-event experiment progress storm into one scheduled refresh", async () => {
    let listener: ((event: { type: "experiment_progress"; session_id: string; round: number; total_rounds: number }) => void) | undefined;
    vi.useFakeTimers();
    mocks.getSession.mockResolvedValue(snapshot);
    mocks.subscribeScientistEvents.mockImplementation(async (next) => { listener = next; return () => undefined; });
    render(<ResearchWorkbench session={session} />);
    await Promise.resolve();
    await Promise.resolve();
    expect(listener).toBeTruthy();
    mocks.getSession.mockClear();
    for (let round = 1; round <= 1000; round += 1) listener?.({ type: "experiment_progress", session_id: "session-workbench", round, total_rounds: 1000 });
    await vi.advanceTimersByTimeAsync(300);
    expect(mocks.getSession).toHaveBeenCalledTimes(1);
  });
});