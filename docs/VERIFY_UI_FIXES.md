# VERIFY_UI_FIXES

Run:

```bash
chmod +x frontend/scripts/verify_ui_contract.sh
./frontend/scripts/verify_ui_contract.sh
```

Interpretation:
- PASS means the contract checks are present.
- FAIL means the CSS still contains selector wars, missing authoritative block markers, or missing rabbit spotlight linkage.

This script is intentionally simple and heuristic-based. It exists to prevent regressions and to prove the contract is still enforced.
