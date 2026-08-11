# Known failures and resolution

Early native E2E attempts connected to a stale `tauri-driver` process and therefore observed the empty `data:,` WebView. The stale test-only processes were stopped. The final test used the release-built ECOMIC executable and passed against the real `http://tauri.localhost/` application window.

The WebdriverIO service emits a teardown warning about clearing a mock store after the session has closed. It does not affect the test result; the E2E process exits with code 0 and reports one passing test. This warning will be removed or suppressed in the dedicated test configuration during later quality work.
