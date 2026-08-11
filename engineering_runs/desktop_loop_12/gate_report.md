# Loop 12 Gate — PASS

The GUI can load the session-bound `final_report.md`, render safe Markdown, copy it, export a stable identical Markdown file to an explicit user-selected `.md` destination, and open its folder in Windows Explorer. The report contains research question, DomainSpec, hypotheses/revisions, experiments, auditable evidence, evaluator-owned final evaluation, Claim Guard, limitations, and reproduction information. It explicitly excludes API keys, Authorization headers, Oracle raw labels and private reasoning.

PASS: Backend test verifies all required report headings, persisted research question, report artifact paths and byte-identical export.
PASS: GUI test verifies rendered Chinese Markdown inside the desktop page.
PASS: Rust report-location command and research-question persistence compile.
PASS: Python 25 passed / 1 expected skip; Node Pi 12 passed; frontend 10 files / 19 tests passed; Rust check; Tauri Release; native E2E 2 specs / 3 assertions.