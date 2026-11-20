# Public official BLS calendar collector

This package is intended only for the separate PUBLIC repository
`srosario036/hermes-h3-public-calendar`, authorized by its owner18Nov2026.
It contains no trading data, private trading code, account identifiers, broker
credentials, GCP credentials, inference tools, or H3 research results.

Files: `collect_bls.py` at repository root and `renew.yml` installed as
`.github/workflows/renew.yml`. Main branch required. Explicit activation variable
`H3_BLS_PUBLISH_ENABLED=true` is required in this exact public repository.
Only standard `ubuntu-24.04` public GitHub-hosted execution is permitted. No
artifacts/cache, larger runners, private runner billing or new subscriptions.

Every2hours at minute17: one official HTTPS monthly BLS request,25sec timeout,
2MB maximum, no redirects, exact table/month/timezone/schema checks. The original
HTML hash, actual acquisition time and <=6hour expiry accompany public rows.
Failure records coverage_unknown but NEVER refreshes the last verified copy.

Potential public data endpoint after deployment:
https://raw.githubusercontent.com/srosario036/hermes-h3-public-calendar/main/site/latest.json

The H3 consumer must validate approved origin, schema, content hash, month and
original acquisition/expiry; a copy/hash is not a BLS cryptographic signature.
The separate v2 validator supports rollover; the existing H3 November-only
importer is NOT silently changed or deployed. Complete consumer integration and
freshness/failure tests are required before any trading GO.

Schedules can be delayed/dropped by GitHub. After expiry or missing input,
coverage stays unknown and trading stays blocked. A calendar shows selected
national releases, not unscheduled news or constituent earnings. Unchanged
content may legitimately receive a new timestamp only after a real new successful
HTTP200 acquisition. Never infer absence from403 or copy old timestamps forward.

Acceptance before operational use: real successful acquisition from this runner,
manual second genuine acquisition (no need to wait2hours), changed acquisition
time/original hash integrity, scheduled trigger present, and expiry/error tests.
If BLS also rejects this IP, record failure; do not switch to unofficial sources.

No deployment or end-to-end success is claimed merely because this code exists.
