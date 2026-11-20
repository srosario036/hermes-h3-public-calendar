# Official BLS iCalendar — 20 November 2026

**Download verified twice. Coverage remains NO-GO. H3 consumer integration is unverified.**

Exact source: https://www.bls.gov/schedule/news_release/bls.ics

| Independent run | Actual response completed UTC | HTTP | Bytes |
| --- | --- | --- | --- |
| [44727010467](https://github.com/srosario036/hermes-h3-public-calendar/actions/runs/44727010467) | 11:22:13.439863 | 200 | 80,672 |
| [44727334590](https://github.com/srosario036/hermes-h3-public-calendar/actions/runs/44727334590) | 11:24:32.074491 | 200 | 80,672 |

Both original bodies have SHA256: 92a350111ace106deaab5584e4084366bd367b594a0d0bad116008d82d63e501.

## Validation

- Complete VCALENDAR 2.0 envelope and balanced components; 313 events and 313 unique UIDs. Valid dates span 3 January 2025 through 30 December 2026.
- Vendor US-Eastern normalized to America/New_York using modern US daylight rules: January UTC-05, July UTC-04. Today 10:00 New York equals 15:00 UTC and 16:00 Madrid.
- All 313 events omit required DTSTAMP. The vendor subset can be parsed, but strict RFC5545 compliance is not asserted. Provider publication timestamps remain unknown.
- Server Last-Modified: 10 June 2026, 16:56:37 GMT. A successful new retrieval does not prove that the content is up to date.
- The [official November list](https://www.bls.gov/schedule/2026/11_sched_list.htm), reviewed at 11:22:53 UTC, has 10 timed releases; the ICS has 9. Missing: **Total Factor Productivity for Major Industries, 20 November, 10:00 America/New_York**. Another included event shares that time, but completeness cannot be asserted.
- This comparison is a pinned review, not an automatic HTML renewal. Its review expires at 17:22:53 UTC. Later ICS acquisitions do not renew the comparison or establish absence of additional events.
- [Original candidates and attempt evidence](site/ics-probe) include hashes, actual acquisition timestamps, headers, triggers and parsed dates. Run 2 revalidates both independently downloaded candidates.
- No candidate was promoted to latest.json. No previous verified latest existed in these runs. The probe never writes latest* and records before/after hashes; failures cannot advance an accepted timestamp. This is not a claim that a real prior verified ICS was recovered during a failure.

## Provider discrepancy investigation

The missing 20 November event is absent from the original downloaded bytes before parsing. The same event name exists in the file for 19 December 2025, so the evidence concerns the specific 2026 release, not a global exclusion of the title by our collector.

The [BLS Weekly Update](https://www.bls.gov/opub/update.htm) independently confirms the 20 November release. [BLS subscription documentation](https://www.bls.gov/help/hlpiCAL.htm) says the ICS contains most national releases, not all, with a tentative Friday update schedule. The verified finding is an official-feed coverage discrepancy. An old Last-Modified is consistent with stale publication but does not prove its internal cause. No calendar entries or source publication times were invented.

The scheduled HTML collector has been retired: renew.yml now exposes manual dispatch only. Its historical HTTP403 evidence and code remain intact. No new HTML retry was executed.

## Scheduled acquisition

The ICS workflow is enabled on main. Temporary five-minute scheduling did not produce an observable scheduled run during this review. The repository API filtered specifically by event=schedule returned total_count=0 at 11:45:53 UTC on20November2026. **Actual scheduled execution remains unverified**, independently of the two successful manual acquisitions.

The temporary schedule has been reduced to **minute 23 every two hours UTC**, using only standard free public runners. No follow-up app automation or paid service was created. GitHub may delay or drop scheduled jobs. Transport success remains separate from coverage_GO=false.

## Concrete next blocker

Resolve the official-source completeness discrepancy and prove the scheduled trigger. Then separately validate the H3 consumer's schema, hash integrity, original acquisition/expiry, publication-time provenance and fail-closed behavior. No coverage GO is granted. No Cloud, trading, inference, subscriptions or alternative download variants were used.
