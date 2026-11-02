# Executed review and milestone disposition

2026-11-02. Builder and verifier: the same Codex agent/session. Independent review NOT_RUN. Acceptance NOT_GRANTED. No governed Base, old desktop, legacy profile, existing release or installed shortcut was changed.

## Executed controls

Final Windows 11 build 26200 / Python 3.12.10 / PySide6-Essentials 6.12.0 run: **14 test methods passed; zero skips and zero failures**, 15.382 seconds. The native Qt widgets pipeline was used, not an HTML mockup or generated illustration. See `evidence/final-tests.log` and `evidence/qualification.json` for exact test identities and source hashes.

1. A known circle was drawn; the viewport's real Qt-grabbed PNG had a verified hash, pixel dimensions and intended-scene provenance.
2. Renderer-only corruption changed that circle to a rectangle while the intended-scene hash stayed fixed. Pixel analysis detected the shape change and nonzero RGBA delta.
3. A missing fixture node was detected; the unmodified fixture had 43 expected and 43 observed eligible markers, with no missing/unexpected markers at the tested default views.
4. Analyzer detachment and a deliberate exception produced UNAVAILABLE results while retaining raw captures. No confidence percentage was fabricated.
5. Disabled observation refused captures while the fixture could still change. A busy worker refused additional capture admission; the GUI has one analysis worker and no unbounded analysis queue.
6. Frame sequence/history, light/dark preference and hidden dock state survived closing/reopening.
7. Workspace draft saving retained the original source bytes. Proposal inspection needed no approval, and a pending proposal reloaded after restart.
8. Retained activity was capped at 2,000 entries and search worked. A 305-file synthetic catalog returned pages of 100. A sparse logical file of exactly 5 GiB was read near its end; larger files were refused. This measures bounded chunk access, not full-file ingestion throughput.
9. Traversal, alternate data streams and junction/reparse scopes were refused. A Python socket-connect refusal control covered detached frontend capture/navigation operations. It is not an OS access audit, comprehensive sandbox proof or permission guarantee against hostile same-user processes.
10. Screenshots were generated at actual logical and physical 1366×768 and 1920×1080, device pixel ratio 1.0. The monitor normally uses 125% scale; the final screenshot run set QT_SCALE_FACTOR=0.8 to exercise those exact physical sizes. An earlier complete 14-test run at native 125% also passed before the added exact-replay/profile-binding controls. Display measurements are retained; native screenshots are not the supplied concept image.
11. A fresh disposable M1.2 process was PAUSED. An authenticated GUI submitted and resumed a synthetic fake-adapter draft, closed while WORKING, and reopened to a committed result while the same coordinator stayed alive. Disabling observation did not stop that runtime. No GUI runtime database was created.
12. A deliberately lost post-commit submission reply produced an UNCONFIRMED record. Exact replay returned a receipt without adding a duplicate job. Changing its profile identity refused replay.

Earlier failed runs are retained. The first run exposed fixture marker scaling and the viewport minimum-size boundary. The second still exposed marker overlap at compact size. Rendering now keeps readable marker sizes, uses smaller fixture ink and distinct non-marker label colors; the full final run passes. No test expectation was weakened to hide these failures.

## Milestones

| Milestone | Candidate implementation and bounded verification |
| --- | --- |
| GUI-1 | Implemented shell, native adjustable/floating docks, saved layout, themes and shortcuts. Formal screen reader/high-contrast review pending. |
| GUI-2 | Implemented passive fixture geometry, layers, replay, selection, pan/zoom. Live engine adapter NOT_IMPLEMENTED. |
| GUI-3 | Implemented actual viewport widget capture, frame provenance, bounded asynchronous analysis, disable/detach controls. Monitor scanout and external-window capture NOT_IMPLEMENTED. |
| GUI-4 | Implemented fixture marker image analysis, comparison, saved PNG/JSON history and explicit errors. General vision, semantic geometry verification and model image interpretation NOT_IMPLEMENTED. |
| GUI-5 | Partial: authenticated M1.2 attach/read/jobs/draft controls; selected read-only source roots; bounded chunk reads; save-new drafts and local proposal review. Legacy chat migration, reference ownership and engine scene binding remain open. |
| GUI-6 | Partial: the listed native regression/recovery/layout controls passed. Broad performance, physical power loss, full accessibility, all supported monitors/Python versions and long soak remain unqualified. |

No milestone is independently accepted or marked FINISHED by this review. Historical runtime holds and acceptance records retain their scope. The bundled M1.2 runtime bytes are unchanged; packaging it for this isolated GUI does not promote it.

## Remaining limits

Widget grabbing renders the widget's content. It does not prove what a monitor, GPU compositor, remote desktop or obstructing window displayed. Capture excludes the observation panel and other applications. A small synchronous Qt grab occurs on the GUI thread; PNG encoding, persistence and image analysis run on a background worker. Sampling is at most twice per second through the public API, and automatic sampling is once every two seconds with busy frames skipped.

The marker analyzer is palette-dependent. Overlap, clipping, selection outlines, extreme zoom or unsupported DPI geometry can create discrepancies. It does not infer semantic nodes, basins, plates, evidence truth or model understanding. There is no cloud or general vision adapter. Captures are never automatically sent to Ollama; only an explicitly submitted text goal and optional selected text preview enter draft IPC.

Workbench evidence uses ordinary local files and QSettings, not the coordinator's transactional storage or DPAPI. PNG/JSON history remains on disk with no automatic eviction; disk usage needs operator management. Only a bounded metadata tail is loaded. Proposal decisions are local records; they do not have governed approval semantics. Up to 100 proposal records are indexed in the GUI; older draft files remain on disk.

Read-only path checks reject ordinary traversal and links but do not defeat all hostile concurrent same-user path replacement races. Selected-root reads are UTF-8 replacement previews; exact chunk hashes refer to bytes, while any submitted text has a separate exact UTF-8 hash. The GUI does not hash or load an entire 5 GiB file into memory. No archive extraction or recursive Library indexing is provided.

Model status reports configured provider only. Runtime/profile validation and authenticated typed IPC remain delegated to the unchanged candidate. Jobs/events are paged; Previous jobs returns to the first page. There is no arbitrary shell, patch application, background acquisition, source overwrite, implicit start/resume, automatic acceptance or model self-authorization route.
