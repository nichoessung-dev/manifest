# Enrichment report

Updated 2026-10-30T00:44:54Z with `claude-opus-5-5` (effort low, Message Batches).

## Coverage

- Labelled finds in the live catalogue: **99 / 9202**
- Labelled entries no longer in the catalogue: 0
- Batches collected: 3, still pending: 10 (8030 requests)
- Open failures: 1073

## Failures by reason

- image_fetch_failed: 1072
- alt_text_too_long: 1

## Token usage and cost

| | tokens |
|---|---:|
| input (uncached) | 86,249 |
| cache read | 88,920 |
| cache write 1h | 216,372 |
| cache write 5m | 0 |
| output (incl. thinking) | 18,920 |

Estimated spend so far: **$1.24** at batch prices (input $2.00/M, output $10.00/M, cache read $0.10/M). Per labelled find: $0.0125.
Projected cost for the remaining 9103 finds: about $113.61.

## Batches

| id | label | created | requests | status | result |
|---|---|---|---:|---|---|
| `msgbatch_01SdrEfemd28WTTrnLsvjP7A` | pilot | 2026-10-29T23:08:14Z | 100 | collected | invalid 2, succeeded 98 |
| `msgbatch_01PpcmNbNiChrkXUv6g7Ki6h` | retry of msgbatch_01SdrEfemd28WTTrnLsvjP7A | 2026-10-29T23:10:19Z | 2 | collected | invalid 1, succeeded 1 |
| `msgbatch_01EXRSWoNL4QHMJFZPcCcthC` | retry of msgbatch_01PpcmNbNiChrkXUv6g7Ki6h | 2026-10-29T23:14:21Z | 1 | collected | invalid 1 |
| `msgbatch_018rhRkk6dVTjTt8zQeJusHc` | full | 2026-10-30T00:43:57Z | 889 | in_progress |  |
| `msgbatch_01Y7DyUWykULGmarRjM5Fugg` | full | 2026-10-30T00:44:04Z | 863 | in_progress |  |
| `msgbatch_01UhD1FpQB3isEhS83ZX2uiq` | full | 2026-10-30T00:44:11Z | 892 | in_progress |  |
| `msgbatch_01R6BJWudpLmZdAE3FsoBpzw` | full | 2026-10-30T00:44:18Z | 861 | in_progress |  |
| `msgbatch_01MsLyiqfUWcpDnBNDZxrK2i` | full | 2026-10-30T00:44:25Z | 900 | in_progress |  |
| `msgbatch_01UdmSQoAHihYVzGqUFgijgG` | full | 2026-10-30T00:44:32Z | 888 | in_progress |  |
| `msgbatch_01BCVU1GoZyBnhA1Kq2XDYB3` | full | 2026-10-30T00:44:39Z | 896 | in_progress |  |
| `msgbatch_01Mp9ZTNRTbpVhN3evNYX1Xq` | full | 2026-10-30T00:44:46Z | 901 | in_progress |  |
| `msgbatch_01PGD9FfaS5cwUPR77sJR2JS` | full | 2026-10-30T00:44:53Z | 869 | in_progress |  |
| `msgbatch_01V4LLoLc12qa3cqaJVq3QMf` | full | 2026-10-30T00:44:54Z | 71 | in_progress |  |
