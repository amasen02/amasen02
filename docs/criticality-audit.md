# OpenSSF criticality audit

The `OpenSSF criticality audit` workflow measures the public, non-fork repositories
owned by `amasen02` with the official
`github.com/ossf/criticality_score/v2/cmd/criticality_score@v2.0.4` command.
It also retains the 30-repository candidate snapshot in
`.github/criticality/targets.json`, so the first measurement covers every target
from the readiness plan even if GitHub discovery changes later.

> **Known upstream limitation:** v2.0.4 can receive a GitHub `/issues` response
> without `rel=last` for repositories with multiple issues or pull requests, then
> wrongly treats the absent last link as a total of zero. Upstream fix
> [#830](https://github.com/ossf/criticality_score/pull/830) is not merged. The
> raw scores therefore may not contain fully correct issue-derived signals; this
> audit does not claim eligibility from those scores. The workflow
> retains an independent paginated issue diagnostic for two representative
> repositories so this limitation remains visible in each hosted run.

The workflow uses the official `original_pike` defaults and one worker with
`-depsdev-disable`. This disables only the optional deps.dev source; it does not
claim deps.dev or BigQuery coverage. The built-in Actions token is exposed to the
collector through `GITHUB_AUTH_TOKEN` and to `gh` through `GH_TOKEN`. Workflow
permissions are read-only.

Raw CSV, collection logs, the command version, UTC timestamp, target discovery,
configuration provenance, and the validated summary are uploaded as one artifact.
Each repository is collected in a fresh official scorer process, with a three
second delay between repositories to stay below GitHub commit-search rate limits.
Per-repository exit status, result presence, CSV, and log are retained; the
aggregate collection step fails when any repository fails. Available per-repository
CSV files are combined only when their headers match exactly, and the summarizer
runs whenever that aggregate raw CSV exists, including after a partial collection.
The summary requires all ten legacy inputs and a finite score in `[0, 1]` for
every expected row. Missing or invalid values are `UNKNOWN`, never zero, and fail
the validation gate. A score is marked `THRESHOLD_MET` using the exact comparison
`default_score >= 0.4`; the displayed score is not rounded for that decision.
This measurement label is separate from software maintenance or any external
qualification program.

The profile repository (`amasen02/amasen02`) is measured for coverage but is
marked ineligible because it is a profile repository rather than a software
candidate. A successful measurement with zero threshold-met eligible scores
explicitly reports that no threshold was met. Any validation failure withholds
threshold and eligibility claims entirely.
