# Known failures

No Loop 9 product-blocking failures. WDIO emits a post-session mock-store cleanup warning after all native assertions pass; it is a test-harness cleanup warning, not an application failure.