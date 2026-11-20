# Official BLS iCalendar — 20 November 2026

**Transport works. Coverage remains NO-GO. H3 consumer integration is not verified.**

Exact official source: https://www.bls.gov/schedule/news_release/bls.ics

| Independent run | Response completed UTC | HTTP | Bytes |
| --- | --- | --- | --- |
| [44727010467](https://github.com/srosario036/hermes-h3-public-calendar/actions/runs/44727010467) | 11:22:13.439863 | 200 | 80672 |
| [44727334590](https://github.com/srosario036/hermes-h3-public-calendar/actions/runs/44727334590) | 11:24:32.074491 | 200 | 80672 |

Both original byte streams: SHA256 92a350111ace106deaab5584e4084366bd367b594a0d0bad116008d82d63e501.

## Validation

- Complete VCALENDAR2.0 envelope and balanced components;313 events,313 unique UIDs; valid dates from3January2025 through30December2026.
- Vendor US-Eastern mapped to America/New_York with US daylight rules: January UTC-05, July UTC-04. Today10:00NY equals15:00UTC/16:00Madrid.
- All313 events omit required DTSTAMP: parsed vendor subset, **not strict RFC5545 compliance**. Publication times remain unknown; no invented timestamps.
- Server Last-Modified10June2026 16:56:37GMT. New acquisition time does not prove current content.
- [Official November list](https://www.bls.gov/schedule/2026/11_sched_list.htm), reviewed20November11:22:53UTC, has10 timed releases; ICS has9. Missing: **Total Factor Productivity for Major Industries,20November10:00 America/New_York**.
- The discrepancy proves incomplete coverage independently of Last-Modified age. Comparison is a pinned manual review, **not automatic HTML renewal**; expires17:22:53UTC. Future acquisitions cannot renew that comparison.
- Original candidates, response metadata, hashes, trigger and validations persist under [site/ics-probe](site/ics-probe). Validation of run2 also rechecks the original run1 candidate.
- No candidate promoted to latest.json. No verified latest existed during these runs. Probe never writes latest*; before/after hashes are recorded. Errors cannot advance an accepted timestamp.

## Scheduled acquisition

Temporary five-minute cron tests a real scheduled trigger. Proof currently pending; cron configuration is not execution evidence. Reduce to two-hour cadence after proof.

## Remaining blocker

Reconcile the ICS with current official release coverage, then separately test the H3 consumer's schema, integrity, original acquisition/expiry and fail-closed behavior. No coverage GO is granted. No Cloud, trading, inference, subscriptions or alternative download variants were used.
