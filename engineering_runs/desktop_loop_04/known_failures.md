# Known failures / limitations

- No user-owned paid Provider key was used in this automated engineering gate. The manual real-provider verification is intentionally `NOT_RUN`, not claimed as passed.
- The current development build still requires local Python and Node runtimes. Runtime bundling and clean-machine verification are reserved for Loops 13–17.
- WebdriverIO reports a post-test mock-store teardown warning (`sessionId required`) after successful native tests. The test command exits successfully and all three native assertions pass; this is tracked as non-product test infrastructure noise.
