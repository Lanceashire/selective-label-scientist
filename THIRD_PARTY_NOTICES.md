# Third-party notices

ECOMIC Desktop bundles the following principal open-source components:

- Tauri 2 and its Windows/NSIS packaging components.
- React, Vite and Recharts for the local desktop interface.
- earendil-works/pi packages for the local agent orchestration runtime.
- Python backend dependencies including DuckDB, NumPy, SciPy, scikit-learn and PyArrow, packaged inside ecomic-backend.exe.

Each component remains subject to its own license distributed in the upstream package metadata. ECOMIC does not embed user API keys in this release; provider credentials are stored through the operating system credential store at runtime.