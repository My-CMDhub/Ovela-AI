# benchmarks

`trace_analysis.json` is the output of `backend/scripts/analyze_trace.py` from
**19 August 2026**, kept exactly as generated because published Bug Smash
write-ups link to it.

**Read it with one caveat.** At the time, the script requested 100 rows sorted
newest-first and read a single page. The file's `span_count` of exactly **100**
is that cap: its `"period": "2h"` label was never verified, and the rows cover
whatever window the newest 100 spans happened to span. The per-span figures in
it are real spans, but they are not a two-hour sample.

The script has since been fixed — it pages to the end of the period, prints the
window it actually read, and reports when Sentry returns a sampled result.
Current figures, with sample sizes and the list of numbers not to quote, are in
[`docs/MEASUREMENTS.md`](../docs/MEASUREMENTS.md).
