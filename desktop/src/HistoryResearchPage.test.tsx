import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
const listSessions = vi.hoisted(() => vi.fn());
const resumeSession = vi.hoisted(() => vi.fn());
const deleteSession = vi.hoisted(() => vi.fn());
vi.mock("./bridge", () => ({ DesktopBridge: { listSessions, resumeSession, deleteSession } }));
import { HistoryResearchPage } from "./HistoryResearchPage";

const entry = { session_id:"session-history", status:"RESEARCH", dataset:"study.csv", dataset_path:"D:/study.csv", domain:"credit", model:"mock", hypothesis_count:2, run_count:1, updated_at:"2026-08-11T00:00:00+00:00", created_at:"2026-08-10T00:00:00+00:00", final_evaluation_revealed:false };
const restored = { session_id:"session-history", status:"RESEARCH", schema:{row_count:10,column_count:2,sample_limit_for_llm:50,columns:{}}, candidates:{}, domain_spec:{historical_decision:{confirmed:true},observation_action:{confirmed:true}}, snapshot:{round_index:3,state:{remaining_budget:8,visible_label_count:4,candidate_remaining:6}}, research_plan_locked:false, final_evaluation_revealed:false };

describe("HistoryResearchPage", () => {
  it("lists local sessions and restores the same persisted session", async () => {
    listSessions.mockResolvedValueOnce({ sessions:[entry] }); resumeSession.mockResolvedValueOnce(restored);
    const onResume = vi.fn();
    render(<HistoryResearchPage onResume={onResume} onExperiments={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByText("study.csv")).toBeTruthy();
    expect(screen.getByText("2 / 1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name:"打开 / 恢复" }));
    await waitFor(() => expect(resumeSession).toHaveBeenCalledWith("session-history"));
    expect(onResume).toHaveBeenCalledWith(restored);
  });
  it("requires a separate confirmation before deleting a session", async () => {
    listSessions.mockResolvedValueOnce({ sessions:[entry] });
    render(<HistoryResearchPage onResume={vi.fn()} onExperiments={vi.fn()} onReport={vi.fn()} />);
    await screen.findByText("study.csv");
    fireEvent.click(screen.getByRole("button", { name:"删除" }));
    expect(screen.getByText("确认删除此 Session？")).toBeTruthy();
    expect(deleteSession).not.toHaveBeenCalled();
  });
});