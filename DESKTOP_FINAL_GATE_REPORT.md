# ECOMIC Desktop Final Gate Report

## Result

```json
{
  "desktop_ready": false,
  "blocking_failures": [
    "Clean Windows VM evidence is missing.",
    "The full Setup-only GUI research journey on a clean machine is not proven.",
    "The prescribed fake-key security exercise and comprehensive artefact scan are incomplete.",
    "The updated GitHub Actions desktop CI has not run remotely.",
    "The live paid Provider manual gate has not been user-confirmed."
  ]
}
```

## Hard gates

| Gate | Status | Evidence |
| --- | --- | --- |
| A: no Python dependency | LOCAL PASS, VM UNVERIFIED | PyInstaller sidecar acceptance with Python removed from PATH. |
| B: no Node/Pi dependency | LOCAL PASS, VM UNVERIFIED | Bundled Node/Pi typed-tool smoke with Node removed from PATH. |
| C: GUI-only complete research | BLOCKED | UI pieces/E2E pass, but full clean-machine journey lacks evidence. |
| D: key leakage | PARTIAL | Credential-store/redaction tests and source scan pass; prescribed end-to-end fake-key scan incomplete. |
| E: Setup-only delivery | LOCAL PASS, VM UNVERIFIED | Final Setup install, app launch and uninstall passed. |

## Final local artifact

- release/ECOMIC-Setup-0.3.0.exe
- SHA-256: 419432fb9acb58cd07eb8f72fe1df9491d47fa575ab81ede8eacf77fa5f503b7

## Required external completion

1. Run the final Setup.exe in a clean Windows VM with no Python, Node, Rust, Git, Pi, npm, pip or project source.
2. Complete one GUI-only research journey there: import dataset, confirm DomainSpec, create Session, run experiment, view timeline/history and generate report.
3. Run the prescribed fake-key security exercise and scan all normal files for the exact key.
4. Push the changes and obtain a green GitHub Actions desktop CI run.
5. If a live Provider claim is needed, the user must explicitly confirm the GUI connection test using their own key.
