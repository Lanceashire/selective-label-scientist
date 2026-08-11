import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
const call = vi.hoisted(() => vi.fn().mockResolvedValue({ research_mode:true, runs:[{run_id:"r1",policy:"Random",budget:5,rounds:2,status:"COMPLETED"}], policy_comparison:[{policy:"Random",budget:5,rounds:2}], final_metrics:null }));
vi.mock("./bridge", () => ({ DesktopBridge: { call } }));
import { ExperimentCharts } from "./ExperimentCharts";
const session = { session_id:"session-chart", status:"RESEARCH", candidates:{}, schema:{row_count:1,column_count:1,sample_limit_for_llm:50,columns:{}}, domain_spec:{} };
describe("ExperimentCharts", () => it("does not render final metrics in research mode", async () => { render(<ExperimentCharts session={session} />); expect(await screen.findByText("Budget Utilization vs Policy")).toBeTruthy(); expect(screen.getByText("Feedback Count vs Budget")).toBeTruthy(); expect(screen.getByText("Policy Comparison")).toBeTruthy(); expect(screen.getByText("Run Trajectory")).toBeTruthy(); expect(screen.getByText("Hypothesis Timeline")).toBeTruthy(); expect(screen.queryByText("Final Evaluation")).toBeNull(); expect(screen.queryByText(/roc_auc/i)).toBeNull(); expect(document.body.textContent?.toLowerCase()).not.toContain("pr-auc"); }));
describe("ExperimentCharts final evaluation", () => it("renders final metrics only after the backend marks evaluation revealed", async () => {
 call.mockResolvedValueOnce({ research_mode:false, runs:[], policy_comparison:[], final_metrics:{roc_auc:0.8123,average_precision:0.701} });
 render(<ExperimentCharts session={session} />);
 expect(await screen.findByText("Final Evaluation")).toBeTruthy();
 expect(screen.getByText("roc_auc")).toBeTruthy();
 expect(screen.getByText("0.8123")).toBeTruthy();
}));