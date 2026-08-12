import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { DesktopErrorBoundary } from "./DesktopErrorBoundary";
import "./styles.css";
import "./dataset.css";

async function bootstrapDesktop(): Promise<void> {
  // WDIO is loaded only by scripts/build-e2e-desktop.ps1. Production builds keep this branch false.
  if (import.meta.env.VITE_E2E_WDIO === "true") {
    await import("./e2e-wdio-bootstrap");
  }
  createRoot(document.getElementById("root")!).render(
    <React.StrictMode><DesktopErrorBoundary><App /></DesktopErrorBoundary></React.StrictMode>,
  );
}

void bootstrapDesktop();