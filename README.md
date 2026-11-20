# Official public BLS calendar evidence

Only public official calendar data and its collector belong here. No trading data, private code, credentials, Cloud access, inference or paid services.

## Current status — 20 November 2026

- Official iCalendar download succeeded twice independently from standard free public GitHub runners. Originals and hashes are in [site/ics-probe](site/ics-probe).
- The ICS is **partial coverage**, not a complete calendar. BLS itself describes it as containing most national releases. See [official subscription documentation](https://www.bls.gov/help/hlpiCAL.htm).
- The November monthly list and the [BLS Weekly Update](https://www.bls.gov/opub/update.htm) include a 20 November event absent from the downloaded ICS. This omission is present in the original bytes, before parsing.
- ICS monitoring has a two-hour steady-state cadence. A configured cron is not proof of a scheduled execution; see [verification status](ICALENDAR_STATUS.md).
- **Repeated scheduled HTML requests have been removed** from renew.yml. The failed run, collector and historical HTTP403 evidence remain available. The HTML collector can be dispatched manually only; no further manual retry was performed here.
- No ICS candidate is published as an accepted latest.json. Download success is separate from complete event coverage and consumer integration.

## Conservative consumption

Positive official events may inform risk blocks. Missing entries never prove that no event exists. A separately verified official calendar review must cover the requested interval; unknown, expired or conflicting coverage cannot clear it.

Keep source bytes, hashes, actual acquisition times and unknown publication times distinct. A hash proves transfer integrity, not a BLS signature. Failures and copies must not advance accepted timestamps. Do not infer full coverage from the count of313 events or from a recent HTTP200 response.

The public runner has no trading or Cloud credentials. It cannot authorize execution. No private consumer implementation is published in this repository.
