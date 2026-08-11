import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("ECOMIC Desktop AppShell", () => {
  it("renders all eight desktop navigation pages", () => {
    render(<App />);
    ["首页", "新建研究", "数据集", "科研工作台", "实验记录", "历史研究", "模型与 API", "系统设置"].forEach((label) => expect(screen.getByTitle(label)).toBeTruthy());
  });
  it("switches page content without a full document reload", () => {
    render(<App />);
    fireEvent.click(screen.getByTitle("数据集"));
    expect(screen.getByRole("heading", { name: "查看导入数据的概要与语义候选" })).toBeTruthy();
    expect(document.querySelector(".app")).toBeTruthy();
  });
  it("switches between dark and light themes", () => {
    render(<App />);
    fireEvent.click(screen.getByLabelText("切换主题"));
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
