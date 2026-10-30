# Enrichment report

Updated 2026-10-30T00:56:09Z with `claude-opus-5-5` (effort low, Message Batches).

## Coverage

- Labelled finds in the live catalogue: **8020 / 9202**
- Labelled entries no longer in the catalogue: 0
- Batches collected: 33, still pending: 0 (0 requests)
- Open failures: 1182

## Failures by reason

- image_fetch_failed: 1072
- description_sentences: 75
- alt_text_too_long: 27
- description_too_long: 8

## Token usage and cost

| | tokens |
|---|---:|
| input (uncached) | 7,170,240 |
| cache read | 23,534,160 |
| cache write 1h | 1,929,564 |
| cache write 5m | 0 |
| output (incl. thinking) | 1,570,452 |

Estimated spend so far: **$40.12** at batch prices (input $2.00/M, output $10.00/M, cache read $0.10/M). Per labelled find: $0.0050.
Projected cost for the remaining 1182 finds: about $5.91.

## Batches

| id | label | created | requests | status | result |
|---|---|---|---:|---|---|
| `msgbatch_018rhRkk6dVTjTt8zQeJusHc` | full | 2026-10-30T00:43:57Z | 889 | collected | succeeded 860, invalid 29 |
| `msgbatch_01Y7DyUWykULGmarRjM5Fugg` | full | 2026-10-30T00:44:04Z | 863 | collected | succeeded 830, invalid 33 |
| `msgbatch_01UhD1FpQB3isEhS83ZX2uiq` | full | 2026-10-30T00:44:11Z | 892 | collected | succeeded 861, invalid 31 |
| `msgbatch_01R6BJWudpLmZdAE3FsoBpzw` | full | 2026-10-30T00:44:18Z | 861 | collected | succeeded 814, invalid 47 |
| `msgbatch_01MsLyiqfUWcpDnBNDZxrK2i` | full | 2026-10-30T00:44:25Z | 900 | collected | succeeded 866, invalid 34 |
| `msgbatch_01UdmSQoAHihYVzGqUFgijgG` | full | 2026-10-30T00:44:32Z | 888 | collected | succeeded 857, invalid 31 |
| `msgbatch_01BCVU1GoZyBnhA1Kq2XDYB3` | full | 2026-10-30T00:44:39Z | 896 | collected | succeeded 859, invalid 37 |
| `msgbatch_01Mp9ZTNRTbpVhN3evNYX1Xq` | full | 2026-10-30T00:44:46Z | 901 | collected | succeeded 877, invalid 24 |
| `msgbatch_01PGD9FfaS5cwUPR77sJR2JS` | full | 2026-10-30T00:44:53Z | 869 | collected | succeeded 831, invalid 38 |
| `msgbatch_01V4LLoLc12qa3cqaJVq3QMf` | full | 2026-10-30T00:44:54Z | 71 | collected | succeeded 66, invalid 5 |
| `msgbatch_01QXZf3M8YfYcHiXCANmW2wJ` | retry of msgbatch_01V4LLoLc12qa3cqaJVq3QMf | 2026-10-30T00:47:04Z | 5 | collected | succeeded 1, invalid 4 |
| `msgbatch_01MBoHmEgMjdKUH1na2tbdPP` | retry of msgbatch_018rhRkk6dVTjTt8zQeJusHc | 2026-10-30T00:49:07Z | 29 | collected | succeeded 16, invalid 13 |
| `msgbatch_01Aut3hSuqBW9orAomZT4V6v` | retry of msgbatch_01Y7DyUWykULGmarRjM5Fugg | 2026-10-30T00:49:10Z | 33 | collected | succeeded 18, invalid 15 |
| `msgbatch_011vKwZ7jQzYXTwUeDx9pTrj` | retry of msgbatch_01UhD1FpQB3isEhS83ZX2uiq | 2026-10-30T00:49:13Z | 31 | collected | succeeded 15, invalid 16 |
| `msgbatch_01GUwbKrkKpFLKE6X5aJJAX6` | retry of msgbatch_01R6BJWudpLmZdAE3FsoBpzw | 2026-10-30T00:49:17Z | 47 | collected | succeeded 26, invalid 21 |
| `msgbatch_014fQLvyypZQbHaFCFJTe8KS` | retry of msgbatch_01MsLyiqfUWcpDnBNDZxrK2i | 2026-10-30T00:49:20Z | 34 | collected | succeeded 20, invalid 14 |
| `msgbatch_01Cej4V17pyYFiETs58Mvn6A` | retry of msgbatch_01UdmSQoAHihYVzGqUFgijgG | 2026-10-30T00:49:24Z | 31 | collected | succeeded 20, invalid 11 |
| `msgbatch_019QYv12mH3iH9rCb24wt5p8` | retry of msgbatch_01BCVU1GoZyBnhA1Kq2XDYB3 | 2026-10-30T00:49:28Z | 37 | collected | succeeded 19, invalid 18 |
| `msgbatch_01FPZF4WpxZyvgMLLhwc3H7G` | retry of msgbatch_01Mp9ZTNRTbpVhN3evNYX1Xq | 2026-10-30T00:49:31Z | 24 | collected | succeeded 8, invalid 16 |
| `msgbatch_01SBwy5U182aGX677PJ8wUKi` | retry of msgbatch_01PGD9FfaS5cwUPR77sJR2JS | 2026-10-30T00:49:34Z | 38 | collected | succeeded 17, invalid 21 |
| `msgbatch_014DMbS5fqBHbwrDhA7B7Qwt` | retry of msgbatch_01QXZf3M8YfYcHiXCANmW2wJ | 2026-10-30T00:49:36Z | 4 | collected | succeeded 1, invalid 3 |
| `msgbatch_01U27bK2EUsGsh2F8wiJ2wFV` | retry of msgbatch_01MBoHmEgMjdKUH1na2tbdPP | 2026-10-30T00:51:38Z | 13 | collected | succeeded 1, invalid 12 |
| `msgbatch_01AFrs3gEiArb1pjNSgBopzQ` | retry of msgbatch_01Aut3hSuqBW9orAomZT4V6v | 2026-10-30T00:51:41Z | 15 | collected | succeeded 7, invalid 8 |
| `msgbatch_01GZi9PfF1yAProun4dEWAQz` | retry of msgbatch_011vKwZ7jQzYXTwUeDx9pTrj | 2026-10-30T00:51:43Z | 16 | collected | succeeded 4, invalid 12 |
| `msgbatch_01DJHPa45eXaqLXeGZX3BKb2` | retry of msgbatch_01GUwbKrkKpFLKE6X5aJJAX6 | 2026-10-30T00:51:46Z | 21 | collected | succeeded 7, invalid 14 |
| `msgbatch_01RVtyezLiEmHEaBkm3gKPfn` | retry of msgbatch_014fQLvyypZQbHaFCFJTe8KS | 2026-10-30T00:51:49Z | 14 | collected | succeeded 2, invalid 12 |
| `msgbatch_01A9cJQYUsPuqryH1GEpqE2m` | retry of msgbatch_01Cej4V17pyYFiETs58Mvn6A | 2026-10-30T00:51:51Z | 11 | collected | invalid 11 |
| `msgbatch_011D8qYiVjqtKwr7437bx1Be` | retry of msgbatch_019QYv12mH3iH9rCb24wt5p8 | 2026-10-30T00:51:53Z | 18 | collected | succeeded 8, invalid 10 |
| `msgbatch_01T4QtKUZzRb3JJwjix4Eczr` | retry of msgbatch_01FPZF4WpxZyvgMLLhwc3H7G | 2026-10-30T00:51:55Z | 16 | collected | succeeded 6, invalid 10 |
| `msgbatch_014HZC6Jhr7bPxiiGdb6teS8` | retry of msgbatch_01SBwy5U182aGX677PJ8wUKi | 2026-10-30T00:51:58Z | 21 | collected | succeeded 4, invalid 17 |
