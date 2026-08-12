import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const call = vi.hoisted(() => vi.fn());
vi.mock("./bridge", () => ({ DesktopBridge: { call } }));
import { DomainSpecWizard } from "./DomainSpecWizard";

const session = {
  session_id: "session-domain-test",
  status: "RESEARCH",
  domain_spec: {},
  schema: { row_count: 20, column_count: 4, sample_limit_for_llm: 50, columns: {
    decision: { dtype: "VARCHAR", missing_count: 0, missing_rate: 0, unique_count: 2, top_values: { reviewed: 10 } },
    outcome: { dtype: "INTEGER", missing_count: 0, missing_rate: 0, unique_count: 2, top_values: { "1": 10 } },
    cost: { dtype: "DOUBLE", missing_count: 0, missing_rate: 0, unique_count: 2, top_values: { "1": 10 } },
    timestamp: { dtype: "TIMESTAMP", missing_count: 0, missing_rate: 0, unique_count: 2, top_values: {} },
  } },
  candidates: { decision: [{ column: "decision", confidence: 0.99 }], target: [{ column: "outcome", confidence: 0.98 }], cost: [{ column: "cost", confidence: 0.9 }] },
};

describe("DomainSpec wizard", () => {
  it("walks a user through non-JSON confirmation and commits one atomic DomainSpec", async () => {
    call.mockResolvedValueOnce({ audit: { status: "OK" } });
    const confirmed = vi.fn();
    render(<DomainSpecWizard session={session} onConfirmed={confirmed} />);
    const next = () => screen.getByRole("button", { name: /下一步/ });
    fireEvent.click(next());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "reviewed" } });
    fireEvent.click(next());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "not_reviewed" } });
    fireEvent.click(next());
    fireEvent.click(next());
    fireEvent.click(next());
    fireEvent.click(next());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "离线回放审核动作" } });
    fireEvent.click(next());
    fireEvent.click(next());
    fireEvent.click(screen.getByRole("button", { name: /确认并版本化/ }));
    await waitFor(() => expect(call).toHaveBeenCalledTimes(1));
    expect(call).toHaveBeenCalledWith("confirm_domain_spec", expect.objectContaining({ session_id: "session-domain-test", decision_column: "decision", observed_values: ["reviewed"], non_observed_values: ["not_reviewed"], target_column: "outcome", reversible: true, simulatable: true, description: "离线回放审核动作" }));
    expect(confirmed).toHaveBeenCalledOnce();
  });
});