# M0.1 Chat Input Integrity — candidate builder return
Date: 2026-10-24. AUTHORITY_EFFECT: NONE. No acceptance, seal or promotion.

Parent: LEVIS_CODE_REVIEW_RC2.zip, SHA-256 8e0d45eacef2815b592d96d01fa072f48efec1b59431520150edcff3d656f786, 5,839,733 bytes. All 54 inspected baseline files matched the archive before changes. Live laptop source remains inaccessible; this is explicitly the authorized inspected-export baseline.

## Reproduction
Original _chat with a 4,001-character user message made one /api/chat generation request containing zero user messages. Candidate regressions were also executed against original RC2 modules in a disposable directory; see M0_1_BASELINE_REGRESSIONS.log for expected failures.

## Change
Only production file changed: levis_desktop.py. _chat finds the newest user instruction, refuses more than 4,000 Python string characters before any API call or library inventory, and bounds preceding contiguous history around that instruction. Saved assistant messages after that newest user are not treated as a replacement instruction when requesting a new response. There is no token/context limit increase.
GUI send reads end-1c (excluding Tk's synthetic final newline), retains user-entered whitespace, persists the entire message before calling chat, and reports refusal through its existing status path. A refused message remains visible and stored; it is not sent or silently shortened. Whitespace-only submissions remain ignored. No model lock, policy, capability dispatcher, permissions, Base or nested foundation changes.

## Actual tests
31 tests passed: original 23 plus 8 new regression methods (with subtests). Exact command/output is in evidence/M0_1_TESTS.log. New checks cover 4,000 acceptance, 4,001 refusal with tools on/off and no API/inventory calls, multi-byte Unicode, older over-budget messages, exact fitting history, latest-instruction retention with trailing stored answers, persistence after refusal and reopen, and the actual nested GUI send callback with mocked widgets/thread startup. The callback is compiled from the source AST to exercise its storage behavior without a display. This is not a visual GUI test.
Downloads and model API calls are mocked by the automated tests; no real model or corpus download occurred. Original RC2 regression failures demonstrate that the new controls detect the prior behavior; these are expected negative-control results, not candidate failures.

## Packaging and custody
M0_1_CHANGED_FILES.json enumerates added/changed/removed files relative to the parent; original tests are preserved with new tests appended. The current manifest covers every candidate regular file except itself. Census self-hash and regenerated manifest hashes are deferred to that manifest and the outer archive, avoiding circular hash claims. Original evidence/RELEASE_VERIFICATION.json and historical logs remain unchanged and describe their historical runs, not this candidate.
The delivery bundle contains the candidate ZIP, its SHA-256 sidecar and this report. Original parent archive is not overwritten. Nested foundation archive is byte-identical to the parent (SHA-256 0e14d41a71bbeac510d2c685ebea6a5662ccbaf9e5f99b567615d2c148a325a0).

## Unresolved residuals
- No live Windows visual GUI, installed Ollama/Qwen, stock-task execution, overnight or power-loss testing in this run. No display or listening Ollama service available here.
- Character budget remains 4,000 code points, not UTF-8 bytes, grapheme clusters or a tokenizer budget. A valid character count does not guarantee the combined 4,096-token prompt fits every input.
- Older context can still be omitted at the first boundary; no summarization or whole-history reasoning is added.
- Oversized input is retained as plaintext history and refused for inference; this is not large-file ingestion.
- Existing same-account/unsigned-bootstrap trust and historical M0 debts remain. New tests do not establish general model behavior or Base acceptance.
- User must supply the live laptop source for any subsequent live-version comparison. No material difference from the accessible inspected baseline was found before this patch.
