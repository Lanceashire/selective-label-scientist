# ECOMIC reference repositories

The runnable source tree uses two read-only reference repositories during local
development. They are intentionally not committed into this repository as
nested Git repositories or copied `node_modules` trees.

```powershell
git clone --depth 1 https://github.com/earendil-works/pi vendor/pi
git clone --depth 1 https://github.com/Lanceashire/LexiRiskLabel vendor/LexiRiskLabel
```

The ECOMIC code treats `LexiRiskLabel` as a frozen reference implementation and
does not modify its phase runners or stored results. Set `ECOMIC_PI_ROOT` or
use the default `vendor/pi` path if a local Pi build is available.
