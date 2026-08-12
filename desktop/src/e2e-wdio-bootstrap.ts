// This module is dynamically imported only in the dedicated E2E build.
// Keeping it separate prevents the WDIO guest runtime from entering the production Vite bundle.
import "@wdio/tauri-plugin";