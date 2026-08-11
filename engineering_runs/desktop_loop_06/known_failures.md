# Known failures / limitations

- WebdriverIO emits a post-test mock-store teardown warning (`sessionId required`) after all native assertions pass. This is test-infrastructure noise, not a runtime failure.
- The current installer is a development-stage bundle and still relies on developer Python/Node runtimes. Fully bundled runtimes and clean-machine validation are deferred to Loops 13–17.
