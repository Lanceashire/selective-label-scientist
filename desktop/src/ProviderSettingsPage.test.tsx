import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  providerStatus: vi.fn().mockResolvedValue({ providers: [{ id: "deepseek", label: "DeepSeek", requires_base_url: false }], profiles: [], default_provider: null }),
  saveProvider: vi.fn().mockResolvedValue({ status: "SAVED", provider: "deepseek", configured: true, masked_key: "••••abcd" }),
  deleteProvider: vi.fn().mockResolvedValue({ status: "DELETED", provider: "deepseek" }),
  validateProvider: vi.fn().mockResolvedValue({ status: "READY_FOR_CONNECTION_TEST", message: "配置检查通过。" }),
  testProviderConnection: vi.fn().mockResolvedValue({ status: "SUCCESS", kind: "success", tool_calling_verified: true, message: "连接成功，模型响应正常，Tool Calling 已验证。" }),
}));

vi.mock("./bridge", () => ({ DesktopBridge: mocks }));
import { ProviderSettingsPage } from "./ProviderSettingsPage";

describe("Provider settings security UI", () => {
  it("only displays the masked credential and clears the input after a save", async () => {
    mocks.providerStatus.mockResolvedValue({ providers: [{ id: "deepseek", label: "DeepSeek", requires_base_url: false }], profiles: [], default_provider: null });
    render(<ProviderSettingsPage />);
    await screen.findByRole("heading", { name: "DeepSeek" });
    fireEvent.change(screen.getByLabelText("Model ID"), { target: { value: "deepseek-chat" } });
    const keyInput = screen.getByLabelText("API Key") as HTMLInputElement;
    fireEvent.change(keyInput, { target: { value: "test-key-abcd" } });
    fireEvent.click(screen.getByRole("button", { name: "安全保存" }));
    await waitFor(() => expect(mocks.saveProvider).toHaveBeenCalledWith(expect.objectContaining({ api_key: "test-key-abcd" })));
    expect(keyInput.value).toBe("");
    expect(screen.queryByText("test-key-abcd")).toBeNull();
    expect(await screen.findByText(/••••abcd/)).toBeTruthy();
  });

  it("accepts a key pasted with Ctrl+V before secure saving", async () => {
    mocks.providerStatus.mockResolvedValue({ providers: [{ id: "deepseek", label: "DeepSeek", requires_base_url: false }], profiles: [], default_provider: null });
    render(<ProviderSettingsPage />);
    await screen.findByRole("heading", { name: "DeepSeek" });
    const keyInput = screen.getByLabelText("API Key") as HTMLInputElement;
    fireEvent.paste(keyInput, { clipboardData: { getData: () => "pasted-key-9876" } });
    expect(keyInput.value).toBe("pasted-key-9876");
    fireEvent.click(screen.getByRole("button", { name: "安全保存" }));
    await waitFor(() => expect(mocks.saveProvider).toHaveBeenCalledWith(expect.objectContaining({ api_key: "pasted-key-9876" })));
  });
  it("requires an explicit confirmation before using the real Pi connection probe", async () => {
    mocks.providerStatus.mockResolvedValue({ providers: [{ id: "deepseek", label: "DeepSeek", requires_base_url: false }], profiles: [{ provider: "deepseek", label: "DeepSeek", model_id: "deepseek-chat", base_url: null, configured: true, masked_key: "••••abcd", tool_calling_verified: false, last_connection_test: null, is_default: true }], default_provider: "deepseek" });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ProviderSettingsPage />);
    await screen.findByText(/当前密钥：••••abcd/);
    fireEvent.click(screen.getByRole("button", { name: "真实连接与 Tool Calling 测试" }));
    await waitFor(() => expect(mocks.testProviderConnection).toHaveBeenCalledWith("deepseek"));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("可能产生极少量 API Token 消耗"));
    expect((await screen.findAllByText(/Tool Calling 已验证/)).length).toBeGreaterThan(0);
    confirm.mockRestore();
  });
});
