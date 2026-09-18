# Decryptors are searched, optimising the ranking metric

For each item the tool evaluates all nine options (eight decryptors plus no decryptor) and picks the winner, reporting which one won alongside the number. The search objective is **ISK per day** — the same metric the list is sorted by (ADR-0006).

Optimising per-unit profit instead would pick a different decryptor: one that lifts margin while cutting BPC runs or invention chance reduces throughput, so it would win on per-unit profit and lose on ISK/day. The inner search must share the outer objective, or the tool selects for a goal the user is not reading.

The search is pure local computation over data already fetched — it does not multiply network calls.
