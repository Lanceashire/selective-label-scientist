# ECOMIC Desktop Engineering Report

## Build metadata

- Product: ECOMIC Desktop 0.3.0
- Build date: 2026-08-11 22:01 +08:00
- Git commit: 77d34fdda43cb8dca4b3883e710d6eaca0f48e72
- Windows build environment: Windows NT 10.0.26200.0
- Tauri: 2.9.5; tauri-build: 2.5.1
- React: 18.3.1
- Pi commit: f858ae3e822489d6ef0fd9f72342b8fc214e9b95
- Python backend build runtime: Python 3.13.13
- Node build runtime: v24.14.0

## Released artifact

- release/ECOMIC-Setup-0.3.0.exe
- SHA-256: 
419432fb9acb58cd07eb8f72fe1df9491d47fa575ab81ede8eacf77fa5f503b7

## Verified local evidence

- Python backend EXE sidecar acceptance passed with Python removed from PATH.
- Bundled Node/Pi typed-tool smoke passed with Node removed from PATH.
- Frontend: 10 files and 19 tests passed using an isolated jsdom Vitest configuration.
- Native Tauri E2E: 2 spec files, 3 assertions passed; after GUI shutdown no ecomic-desktop or ecomic-backend process remained.
- NSIS Setup install, installed desktop launch and uninstallation passed for the final artifact.
- Provider keys are kept in Windows Credential Manager and redaction/secure-contract tests pass.
- Provider Probe now has a 15-second timeout and terminates its bundled Node process before returning a safe Chinese error.

## Evidence limitations

- A true clean Windows VM without developer tooling and project source has not been provided, so Gate 17 is not passed.
- The exact prescribed fake-key end-to-end sequence through connection, Agent run, crash, report and full filesystem scan has not completed; Gate 18 is not passed.
- The new desktop CI workflow is configured locally but has not yet run on GitHub Actions.
- A live paid Provider test remains user-controlled and has not been invoked automatically.
