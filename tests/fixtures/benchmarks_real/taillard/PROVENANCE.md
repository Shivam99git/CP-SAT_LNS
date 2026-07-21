# Taillard job-shop benchmark instances

Downloaded 2026-07-12 from the ScheduleOpt/benchmarks GitHub repository
(https://github.com/ScheduleOpt/benchmarks/tree/main/jobshop/instances/text/Taillard1993),
which redistributes Taillard's (1993) classic large-scale job-shop instances
in the same plain-text format as `../PROVENANCE.md`'s OR-Library set (no
loader changes needed -- `load_taillard_style` parses both).

20 files: `ta01`-`ta20` (`ta01`-`ta10`: 15x15, `ta11`-`ta20`: 20x15) --
meaningfully larger than the existing OR-Library set's max of 20x10, giving
real-instance coverage at sizes comparable to and beyond the synthetic
`paper_main` experiment's largest size (20x20).

`../taillard_bks_reference.json` is the repository's published best-known-solutions
table (`jobshop/solutions/bks.json`, dated in-file 2026-06-01, computed with
OptalCP) for every instance in the repo, not just Taillard's -- kept for
cross-validation. All 20 `ta01`-`ta20` entries are `"status": "closed"`
(proven optimal), e.g. ta01=1231, ta02=1244, ..., ta20=1348.

## Validation performed

`ta01` was solved with our `load_taillard_style` + CP-SAT pipeline and
**matched the published optimum exactly (1231), proven `OPTIMAL` in 15s**,
with independent solution validation passing.
