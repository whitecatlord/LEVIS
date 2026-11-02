# Start LEVIS — library and bounded tools

Double-click **Start LEVIS** on this computer's desktop, or `START_LEVIS.cmd` in this package. Close an older LEVIS window and reopen it to load the changes. Your conversation history is preserved.

## Installed library

The **Library & tools** tab lists installed sources, searches local text and shows attribution, source URLs, temporal labels and SHA-256 hashes. The first snapshot has **67 sources: 56 historical works and 11 versioned Python tutorial documents**. This is an explicitly scoped starting library, not the full recovered Collegium design or a claim of worldwide or contemporary coverage.

The original boot-packet ID table supplied the historical seed. Seven IDs pointed at mismatched works. Five were corrected by title/author lookup in the official Gutenberg catalog; two remain blocked for edition/scope review. Another 118 historical table entries lack identifiers and remain explicitly unresolved. The complete original 500-item registry has not been recovered; these counts describe the available PG table, not a complete inventory of all missing works.

`collegium/catalog.json` records the corrections, blocked entries, metadata, download URLs, source provenance and pinned raw-byte hashes. Historical catalog labels are retained separately from supplier work/edition identities. Do not collapse multiple editions into independent evidence. Four mathematics/philosophy works are stored as TeX source, never compiled. One work is HTML with attributed search-text extraction. Original bytes remain available; external figures, full typography and image assets are not installed. Search offsets refer to decoded search text, not raw-byte offsets. Sources can be outdated, biased or wrong.

The local library is under `%LOCALAPPDATA%\LEVISStarter\collegium`. Original source bytes are stored by SHA-256; the SQLite search index and append-only acquisition/tool-attempt rows are separate from Base state. This storage is not encrypted, signed, or tamper-proof against same-account software. Retrieval checks the original source hash, but the index/metadata and trusted bootstrap remain within the local-user trust boundary.

## Automatic acquisition

The installer follows the fixed shipped catalog. On startup, missing entries are downloaded and indexed in the background; **Install missing pinned texts** retries missing/failed acquisitions. Existing valid sources are reused. Changed upstream bytes or tampered installed originals are refused rather than silently replaced. A changed catalog needs a separately reviewed new snapshot. No paywalls, authentication gates, or access restrictions are bypassed.

Gutenberg downloads use its listed dedicated mirror, with bounded requests and pacing. The user-authorized installer can fetch only the catalog's restricted HTTPS reference paths, with size and content/identity checks. Source texts are data and never executed. Raw Python documentation comes from the pinned CPython v3.12.10 tag. Preserve source headers and license notices. Gutenberg's USA public-domain assertions are supplier claims, not a worldwide rights warranty. Hilbert's historical 1902 copyright notice was reviewed against the supplier's explicit US public-domain entry and retained.

This ZIP contains the app, pinned catalog and evidence; installed corpus bytes live separately in the local library. On another computer the fixed installer reacquires matching bytes. If upstream files have changed, the installer records a refusal; no unreviewed replacement is installed. Model weights also remain separately installed in Ollama.

## Available tools

The standard-library tool provider is installed with the app; no extra pip packages, arbitrary executables or privileged software installers are needed.

| Tool | Access |
| --- | --- |
| Library search | Model or human: bounded local excerpts with source identity, hashes and status |
| Source reader | Model: installed source ID and bounded character range; no arbitrary paths |
| Calculator | Model or human: bounded numeric arithmetic; no functions, attributes, imports or exponentiation |
| File hash | Human selects an ordinary file up to 64 MiB; file content is not sent to the model |
| Pinned-source installer | Fixed startup/human action; no model installation tool |
| Existing stock task | Explicit human action through the unchanged WSL foundation |

The **Enable local reference tools** checkbox disconnects model-requested tools. Each reply has at most two allowed calls. Unknown tools, extra arguments, unsafe calculator syntax and arbitrary URLs/paths are refused. `collegium/tools.json` pins the provider hash. A generated command is not run merely because it appears in a reply or source document. The model cannot browse the web, install software, use a shell, choose arbitrary local files, click the stock panel, grant a lease or promote evidence.

Try: “Use your calculator to compute (127+83)*19.” Or: “Search the local library for first disobedience and cite a short excerpt.” The footer reports which local tools were requested; actual execution results and failures are retained in the tool ledger. A model may still quote or interpret a source incorrectly: inspect the Library tab and source offsets.

These are **workbench-policy tools**, not a new claim of Base Supervisor lease integration, completed Boot Range qualification, unrestricted FULL_COLLEGIUM_READ, independent assurance or safety verification. The unchanged accepted Base and adopted stock runner remain a separate frozen foundation. The recovered Collegium/Boot Range design still has substantial unimplemented scope.

## Conversation and model

Qwen3.5-4B runs through local Ollama at `127.0.0.1:11434`. Its exact digest is pinned in `MODEL_LOCK.json`. There is no cloud fallback or automatic weight training. LEVIS starts the installed local Ollama service when necessary. The system prompt guides tone and source handling; it is not an enforcement proof. The code-level dispatcher controls tool access.

Sessions are saved in `%LOCALAPPDATA%\LEVISStarter\conversation.sqlite3`. Only recent conversation context (up to 4,000 characters plus bounded tool output, within a 4,096-token model context) is supplied; full history remains visible and exportable. Conversation, retrieved references, tool results, and Base truth remain distinct. Closing the app stops its foreground work. Ollama may remain available; the app requests model unloading after replies.

## Verification and development

`evidence/` retains acquisition failures and later repair receipts, source identity corrections, actual model/tool smoke probes and test results. A failed first mirror request is not erased by a later successful alternate-format acquisition. An acquisition race during the two bounded workers was refused by SQLite's unique source ID constraint; final inventory and source hashes determine the installed state.

Run `python -m unittest discover -s . -p "test_*.py" -v`. Checks cover source pinning, idempotent install, tamper refusal, unpinned/wrong-source refusal, URL/path restrictions, calculator safety, model identity, persistence, forged commands, tool-disable enforcement, and call budgets. Passing examples establish checked behavior in this environment, not universal model compliance.

The complete original foundation release is preserved under `foundation/`. Development records and current tool changes do not rewrite that acceptance history. Future write-capable tools need an explicit capability contract, isolation, idempotency/recovery semantics and separate review before exposure.

Sources: [Gutenberg robot policy](https://www.gutenberg.org/policy/robot_access.html), [official mirrors](https://www.gutenberg.org/MIRRORS.ALL), [machine-readable catalog](https://www.gutenberg.org/ebooks/offline_catalogs.html), [Python license](https://docs.python.org/3.12/license.html), [Qwen model card](https://huggingface.co/Qwen/Qwen3.5-4B).

## Away work: selected files to saved proposals

Open the **Away work** tab. Describe a small job, choose input files, click
**Start task**, then enable **Work through queue**. Minimize LEVIS or click
its window close button; both keep the application alive on the taskbar.
Use **Quit LEVIS** in Away work to exit. Your PC must remain awake and logged in.
There is no startup-at-login registration or Windows background service.

LEVIS snapshots explicitly selected UTF-8 text/code files at queue time and
records their original paths and SHA-256 values. Inputs are limited to 48 KB per
file and 10,000 characters combined; the job brief is limited to 3,000 characters.
PDFs, images, Office documents and binary files are not supported. ZIP source
archives can be reviewed as separate parts using the ZIP workflow below. Avoid selecting credentials or secrets.

Each queued job receives one bounded local-model response. It produces either a
`draft.md` containing an explanation and proposed code, or a `question.md` when
clarification is needed. Select a **NEEDS_ANSWER** job, enter a reply below the
result, and click **Answer selected question**. Other pending jobs can continue.
**Open saved drafts** opens the jobs folder. Local records are plaintext under
`%LOCALAPPDATA%\LEVISStarter\away-work` (or `LEVIS_DATA_DIR`). Provenance includes
input snapshots, hashes and the pinned model lock; it is not signed Base evidence.

Jobs persist across restarts. Processing starts paused each launch. Interrupted
jobs require the explicit retry button; they are not silently replayed. Pausing
stops new jobs after an active model request finishes. A completed result or
question requests taskbar attention; no voice, email or remote notification is
sent. One application instance is allowed per Windows session, and model calls
from conversation and the work queue are serialized to limit RAM pressure.

This is a **draft-producing workflow**: it does not modify original files, apply
patches, execute model-generated code, run tests, install dependencies, or grant
Base capabilities. The away worker does not call the reference-library tools yet.
Code suggestions need review and execution/testing in a separately authorized
workspace. Prompt guidance does not prove behavior or safety. Source contents
and generated proposals never become shell commands in this adapter.

Validation: 18 automated tests passed, including snapshot preservation, separate
draft output, question status, restart interruption and malformed result rejection.
A live local Qwen request corrected a sample subtraction-as-addition bug and saved
a code proposal. The proposal's test was not executed. Hidden-widget construction
passed; no visual layout review, long-duration soak test or independent safety
qualification was performed for Away work.

## Give LEVIS a ZIP of his own source

1. Quit the existing LEVIS app with **Away work → Quit LEVIS**, then reopen
   **Start LEVIS** to load this update.
2. In **Away work**, write a narrow brief such as: “Review the supplied source.
   Explain its purpose, identify one concrete bug if present, and propose a patch.
   List missing context and checks still needed.”
3. Click **Choose ZIP contents** and select `LEVIS_STARTER_2026-10-22.zip`, or
   another ZIP containing the project source.
4. Select rows marked **Text/code** (Ctrl-click for multiple selections), then
   **Use selected members**. Start with a relevant module and its tests.
5. Click **Start task**, enable **Work through queue**, and minimize LEVIS.
   Read results or answer a blocked job using **Answer selected question**.

The archive is inspected in memory, not extracted. Selected UTF-8 text/code
members are saved as snapshots with archive and member SHA-256 values. A changed
archive is rejected if it no longer matches the selection. Files over 6,000
characters become separate jobs with part numbers, character offsets and source
line starts. For ZIP reviews, LEVIS asks for concrete defects with exact quoted
evidence, impact, failure condition and a proposed fix. Before saving a review,
the app checks that each quoted excerpt occurs verbatim in that exact snapshot
and calculates its line number. Unsupported or malformed findings are filtered
out. This checks citation presence only; it does not prove the model's reasoning
or the finding's correctness.

Each segment is still reviewed independently, without whole-repository model
context. **Update / open ZIP review summary** creates one report for the selected
ZIP run with the archive hash, per-file segment statuses, accepted segment
reviews, questions and failures. It is an index and aggregation, not cross-file
model synthesis. Failed or unanswered segments remain visible, and a missing
finding is not evidence that the project is bug-free. Targeted follow-up with
related source and tests may still be needed.

Limits: ZIP up to 64 MiB; at most 2,000 entries and 100 MiB declared contents;
supported text members at most 2 MiB each and compression ratio at most 200;
maximum 100 queued parts per selection. Encrypted archives, unusual compression,
symlinks, unsafe/duplicate member names and malformed input are refused. Nested
ZIPs, model weights, executable binaries, PDFs and images are not recursively
read. Instructions inside source/documents are data, not new permissions.

Reading his own code does not update his running application or model weights.
He can save review notes and proposed replacement code in `draft.md`; applying
those changes and running tests remains a separate step. Historical foundation
bytes and Base governance remain unchanged. No additional safety qualification
is claimed.

ZIP validation: all 23 automated tests passed, and actual archived desktop code
reconstructed byte-for-byte from its snapshots. ZIP selection and queue controls
passed a hidden-widget interaction check. A live source-reading job asked a
clarification question and saved a draft after an answer, but misinterpreted a
test fixture write as a worker-side change. This is direct evidence that model
code reviews can be wrong even when the supplied source is intact. No model
review accuracy guarantee is claimed.

Task controls update: write new instructions in the labelled top task box and
click **Start task** (or Ctrl + Enter). This saves the job and enables processing.
The bottom field is only for answering a selected NEEDS_ANSWER job, and stays
disabled otherwise. **Choose input files** also accepts a single ZIP and opens
the member picker. Restart the app with **Quit LEVIS**, then **Start LEVIS**;
the window title includes **ZIP tasks** when this version is running.
