import { browser, expect } from "@wdio/globals";

describe("ECOMIC Provider security", () => {
  const acceptanceSecret = process.env.ECOMIC_ACCEPTANCE_KEY;

  it("stores the key in Windows Credential Manager, shows only a mask, and clears it", async () => {
    if (!acceptanceSecret) throw new Error("ECOMIC_ACCEPTANCE_KEY is required for the local security acceptance test.");
    const masked = `••••${acceptanceSecret.slice(-4)}`;
    await browser.$('button[title="模型与 API"]').click();
    await (await browser.$('button*=DeepSeek')).click();
    const keyInput = await browser.$('input[type="password"]');
    await keyInput.waitForDisplayed({ timeout: 15_000 });
    await keyInput.setValue(acceptanceSecret);
    await (await browser.$('button*=安全保存')).click();
    await expect(await browser.$(".form-notice")).toHaveText(expect.stringContaining(masked));
    await expect(keyInput).toHaveValue("");
    await expect(await browser.$("body")).not.toHaveText(expect.stringContaining(acceptanceSecret));
    await (await browser.$('button*=清除凭据')).click();
    await expect(await browser.$(".form-title p")).toHaveText("尚未保存 API Key");
  });

  it("rejects an incomplete Custom OpenAI-Compatible configuration before storing a key", async () => {
    if (!acceptanceSecret) throw new Error("ECOMIC_ACCEPTANCE_KEY is required for the local security acceptance test.");
    await browser.$('button[title="模型与 API"]').click();
    await (await browser.$('button*=Custom OpenAI-Compatible')).click();
    await (await browser.$('input[placeholder="例如 deepseek-chat"]')).setValue("test-model");
    await (await browser.$('input[type="password"]')).setValue(acceptanceSecret);
    await (await browser.$('button*=安全保存')).click();
    await expect(await browser.$(".form-notice")).toHaveText("Custom OpenAI-Compatible 必须填写 API Base URL。");
  });
});
