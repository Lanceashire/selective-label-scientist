import { browser, expect } from "@wdio/globals";

describe("ECOMIC DesktopBridge", () => {
  it("clicks backend status in the native Tauri WebView and renders the sidecar response", async () => {
    await expect(browser).toHaveTitle("ECOMIC Desktop");
    const button = await browser.$("button.health-button");
    await button.waitForDisplayed({ timeout: 15_000 });
    await button.click();
    await expect(await browser.$(".card h3")).toHaveText("正常");
    await expect(await browser.$(".card small")).toHaveText("数据库：正常 · Agent Host：未启动");
  });
});
