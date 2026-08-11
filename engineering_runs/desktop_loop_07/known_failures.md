# Known failures / limitations

No Loop 7 product-blocking failures are known from the executed tests.

The WDIO/Tauri test service emits a teardown warning (`Failed to clear mock store: sessionId required`) after the browser session has already completed. This is a test-service cleanup warning: all native test assertions passed and the process exited successfully. It does not originate from the shipped ECOMIC application. It remains tracked for test-harness cleanup.

A live third-party model run requires a user-owned API key and is therefore a later manual acceptance item; it was not substituted for the automated Mock Provider Gate.