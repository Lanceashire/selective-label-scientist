import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi, describe, expect, it } from "vitest";

const mocks = vi.hoisted(() => ({ healthCheck: vi.fn().mockResolvedValue({ status: "OK", backend: "正常", database: "正常", agent_host: "未启动", request_count: 1 }) }));
vi.mock("./bridge", () => ({ DesktopBridge: { healthCheck: mocks.healthCheck } }));
import { App } from "./App";

describe("DesktopBridge health UI", () => {
  it("clicks through the bridge and renders the sidecar health response", async () => {
    render(<App />); fireEvent.click(screen.getByRole("button", { name: "后端状态" }));
    await waitFor(() => expect(mocks.healthCheck).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("heading", { name: "正常" })).toBeTruthy(); expect(screen.getByText("数据库：正常 · Agent Host：未启动")).toBeTruthy();
  });
});
