import React from "react";
import { createRoot } from "react-dom/client";
import "@wdio/tauri-plugin";
import { App } from "./App";
import "./styles.css";
import "./provider.css";
import "./dataset.css";

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
