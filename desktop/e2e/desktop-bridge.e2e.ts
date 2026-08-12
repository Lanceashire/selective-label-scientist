import { browser, expect } from "@wdio/globals";

type RuntimeProbe = { href: string; readyState: string; scriptCount: number; tauri: string; wdio: string; execute: string };

describe("ECOMIC DesktopBridge", () => {
  it("initializes the dedicated WDIO bridge before UI assertions", async () => {
    const probe = await browser.execute(() => ({
      href: window.location.href,
      readyState: document.readyState,
      scriptCount: document.scripts.length,
      tauri: typeof (window as Window & { __TAURI__?: unknown }).__TAURI__,
      wdio: typeof (window as Window & { wdioTauri?: unknown }).wdioTauri,
      execute: typeof (window as Window & { wdioTauri?: { execute?: unknown } }).wdioTauri?.execute,
    })) as RuntimeProbe;
    console.log(`ECOMIC_E2E_RUNTIME_PROBE=${JSON.stringify(probe)}`);
    expect(probe.readyState).toBe("complete");
    expect(probe.wdio).toBe("object");
    expect(probe.execute).toBe("function");
  });

  it("renders the sidecar health state in the native Tauri WebView", async () => {
    await expect(browser).toHaveTitle("ECOMIC Desktop");
    const button = await browser.$("button.health-button");
    await button.waitForDisplayed({ timeout: 15_000 });
    await button.click();
    const healthHeading = await browser.$(".card h3");
    await browser.waitUntil(async () => (await healthHeading.getText()) === "正常", {
      timeout: 35_000,
      timeoutMsg: "Bundled backend did not become ready after its cold start window.",
    });
    await expect(healthHeading).toHaveText("正常");
    await expect(await browser.$(".card small")).toHaveText("数据库：正常 · Agent Host：未启动");
  });

  it("executes a non-health desktop_bridge RPC and receives the business object", async () => {
    const result = await browser.tauri.execute(async ({ core }) => core.invoke("desktop_bridge", { action: "list_sessions", payload: {} })) as { sessions?: unknown };
    expect(Array.isArray(result.sessions)).toBe(true);
  });
});