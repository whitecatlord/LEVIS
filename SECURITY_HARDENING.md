# LEVIS Workbench security hardening

[Download the source handoff and SHA-256 checksum](https://github.com/whitecatlord/LEVIS/releases/tag/workbench-security-hardening).

The Windows dashboard now uses short-lived, single-use launch tickets, a total HTTP request deadline, and explicit refusal of malformed authentication. The coordinator keeps its listener available when the protected bridge fails or its queue is full. Bridge shutdown reports success only after the owned process exits.

The candidate passed 71 Python tests and 26 frontend checks. Live verification exercised an authenticated restart, the protected core snapshot, cross-origin refusal, launch-ticket replay refusal, and malformed authorization. Frontend automation used a DOM/API double. Independent review remains open.

The archive contains code, engineering plans, tests and lineage. It expects an existing compatible protected core in Ubuntu WSL. The source handoff describes the pinned core inputs required for a fresh installation. Historical engineering records in this branch were redacted where local account paths appeared. The manifests describe the resulting public copies.
