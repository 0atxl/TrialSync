# Dependency security exceptions

**Reviewed:** 2026-08-13
**Scope:** Temporary, narrowly bounded exceptions used by `make audit` and CI.

## `PYSEC-2026-3552` — transitive `cryptography`

| Item | Decision |
|---|---|
| Affected installed version | `cryptography==49.0.0` |
| Patched version | `50.0.0` |
| Dependency path | `data-designer==0.8.0` → `data-designer-engine==0.8.0` → `cryptography` |
| Upstream constraint | `data-designer-engine` requires `cryptography>=48.0.1,<=49` |
| Latest compatibility check | Data Designer 0.9.1 was the latest release checked and retains the same `<=49` cap |
| Audit handling | `pip-audit --ignore-vuln PYSEC-2026-3552` only |

The advisory concerns distinguishable failure behavior in attacker-driven PKCS#7 envelope
decryption. TrialSync does not expose PKCS#7 decryption, an S/MIME gateway, or any endpoint that
decrypts attacker-supplied encrypted envelopes. `cryptography` is present only through the offline
Data Designer research dependency; the accepted R3 sampler/expression route performs local tabular
generation and makes no hosted model requests.

Forcing `cryptography==50.0.0` breaks Data Designer's declared dependency contract, and upgrading
from Data Designer 0.8.0 to 0.9.1 does not remove the cap. The project therefore keeps the newest
compatible `cryptography` release, ignores only this advisory ID, and continues to reject every
other Python advisory.

Remove this exception and upgrade `cryptography` as soon as a tested Data Designer release permits
50.0.0 or newer. Recheck the constraint before the final project-delivery audit and whenever the
R3 generator dependency is upgraded. If TrialSync ever introduces PKCS#7 decryption or processes
untrusted encrypted envelopes, this exception becomes invalid immediately.
