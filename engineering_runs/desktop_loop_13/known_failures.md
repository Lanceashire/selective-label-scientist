# Known failures

No Loop 13 product-blocking failures. PyInstaller analysis warns about optional test/dev submodules (pytest, torch) and an optional SciPy hidden import; the independently packaged runtime passes the required backend smoke workflow without Python on PATH.