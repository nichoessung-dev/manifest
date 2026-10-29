# data/enrich

Claude vision labels for catalogue finds, made by `scripts/claude_enrich.py` and run by
`.github/workflows/enrich.yml` (Actions tab, "Enrich finds (Claude)"). Model `claude-opus-5-5`,
effort low, Message Batches API (half price). Nothing here is read by the site yet.

## Files

- `enrich.json`: labels keyed by product id: `item_type`, `colours` (1 to 3), `material` (or null),
  `pattern`, `logo_visible`, `fit` (or null), `alt_text` (110 chars max), `description`
  (two sentences, 260 chars max), `confidence` (0 to 1), plus `model`, `at`, `img`.
- `batch_state.json`: submitted batch ids, which products each holds, attempts per product,
  running token usage and cost.
- `failures.json`: products whose last attempt failed, with the reason. Retried automatically
  up to 3 attempts unless the reason is a refusal or an invalid request.
- `report.md`: coverage, failures by reason, token usage, cost so far and projected cost.
- `dryrun/`: local dry-run output, git-ignored.

## Running

1. Actions, "Enrich finds (Claude)", Run workflow, mode `pilot`, n `100`.
2. The job submits, commits the batch id, then polls for up to 115 minutes and commits results.
3. If the batch is still running when the job ends, the schedule (every 3 hours) collects it,
   or run mode `status`. If a manual run shows "cancelled" in the Actions list, run it again
   (GitHub keeps only one waiting run per group); nothing is lost.
4. Read `report.md`, spot-check `enrich.json`, then run mode `full`.

## Spending cap

`max_cost` caps the TOTAL: already spent + batches still running + what this run would submit.
The per-find price is the rough estimate, or the measured cost so far plus 20 percent once that
is higher. Empty means 60 USD for pilot and full; status and scheduled runs reuse the last cap
given to pilot or full, and retries are skipped when they would go over it. `max_items` limits
how many finds one `full` run submits.

Local check without any API call: `python3 scripts/claude_enrich.py dry-run --image-mode url`
(writes `dryrun/requests_pilot_url.jsonl` and prints a token and cost estimate).

## Checks applied to every answer

JSON schema (fixed lists for type, colours, material, pattern, fit), no em or en dash, length
limits, no quality or legitimacy words (authentic, 1:1, premium and similar), at most two
sentences, confidence between 0 and 1. Anything that fails is retried, not saved.

Low-confidence answers (below 0.5) pass these checks and are saved. Anything that uses
`enrich.json` on the site must filter on `confidence` first.
