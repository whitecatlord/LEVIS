# Contribute a bounded bridge

1. Identify one engineering level and pin the exact parent artifact.
2. Explain the gap, the intended interface and the smallest proposed change.
3. Record dependencies, acceptance tests, negative controls and rollback.
4. Work in a separate candidate; preserve parent source and failed evidence.
5. Show failing-before and passing-after results for a repair. Distinguish executed results from inherited claims.
6. Attribute the builder and reviewer. Do not claim independence when they are the same agent/session.
7. Update scoped completion only when the declared gates are supported. Keep contradictions and residuals visible.

First useful target: the revision/event inconsistency and malformed-receipt replay failures in the M1.1 final review. Durable jobs depend on a reliable ledger.

Do not include personal chat archives, credentials, live profiles, model weights, or unrelated documents in contributions. A draft or bridge proposal is not permission to execute commands or expand capabilities.


## Public contributions and searchable discussion

Start or reply to a public [Discussion](https://github.com/whitecatlord/LEVIS/discussions) for questions and experiments. [Issues](https://github.com/whitecatlord/LEVIS/issues) accept defect reports and bounded bridge proposals; forks and pull requests accept code or documentation changes for review. A GitHub account is needed to post. Include a clear title, experiment ID, exact parent commit/hash, evidence, and unknowns. Summarize important replies in the main post and link corrections to their predecessors. Public posts and replies are readable by others; external indexing and indexing of every reply are not guaranteed. [Communication lab entry point](../lab/communication/README.md).

To search public discussion replies, use the Discussions search box with `in:comments` and your keyword, or GitHub search with `repo:whitecatlord/LEVIS in:comments KEYWORD` and the Discussions result type. For issue replies use the same query with the Issues result type. Omit `in:comments` to search title, body, and comments together. See [GitHub discussion search syntax](https://docs.github.com/en/search-github/searching-on-github/searching-discussions).
