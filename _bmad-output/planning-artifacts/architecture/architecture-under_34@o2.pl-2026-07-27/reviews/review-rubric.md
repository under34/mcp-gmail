# Rubric Review — Architecture Spine: Usługa MCP dla Gmaila

## Gate verdict

**NOT READY — resolve the four high findings before handoff.** The spine has a clear local, hexagonal MVP boundary and the mechanical gate is clean, but it leaves independently built use cases free to implement materially different consent, deletion and operational behavior. Its named technology set also is not reproducibly verified or pinned.

## Evidence checked

- `ARCHITECTURE-SPINE.md`, initiative altitude, against its declared source PRD.
- `prd.md`, FR-1–FR-10 and NFR-1–NFR-5.
- Deterministic lint: **pass** (no placeholders, duplicate/non-monotonic AD IDs, missing AD fields, or blank Stack versions). This does not treat prose such as `current compatible release` as an actual pin.
- Current package records checked 2026-07-27: OpenAI Python is `2.46.0`, so the stated `2.38.0 or compatible locked update` is neither current nor an exact bound. MCP Python SDK v1 is production-recommended while v2 is pre-release; the spine does not select a compatible line or FastMCP API surface. Google client and Anthropic rows are also unpinned. See the package sources: [OpenAI Python](https://pypi.org/project/openai/), [MCP Python SDK](https://pypi.org/project/mcp/), [Anthropic Python](https://pypi.org/project/anthropic/), [Google API Python client](https://pypi.org/project/google-api-python-client/).

## Critical and high findings

### High — The required consent protocol is stated but not enforceable

**Evidence:** AD-5 says that one-off `summarize_gmail` filters are “previewed and confirmed”; the PRD additionally requires confirmation before fetching thread bodies (FR-7), before sending a selected thread to both providers (FR-8), and provider disclosure before every analysis (FR-10). AD-2 binds only three MCP tool names and gives no request/response protocol for a preview, confirmation, expiry, or stale-preview rejection.

**Why it diverges:** One implementer can treat a `confirm=true` field as sufficient, another can fetch bodies while producing the preview, and another can let a confirmation apply after the filter/provider/thread changed. All can appear to meet AD-5 while violating the data-control boundary.

**Disposition: autofix.** Add one AD that binds a two-step, server-enforced analysis authorization contract: a preview uses metadata only and returns an opaque, short-lived approval token bound to the account, resolved filter or thread ID, provider set and content revision; execution requires that token and rejects any mismatch/expiry before body fetch or provider call. Bind it to FR-7–FR-10 and specify the tool schemas or name the application Port that owns them.

### High — Local operational/environmental envelope is materially silent

**Evidence:** The Stack says only “local operating-system cron invoking the CLI”; AD-3 supplies an in-process/per-account local lock. The PRD requires a local 08:00 schedule, configurable local time, a visible failed/partial prior run and manual-tool availability despite scheduler failure (FR-5). There is no decision for supported OS/runtime installation, application-data path derivation, timezone/DST semantics, overlapping cron invocations, missed runs while the machine sleeps, exit-code/error recording, or how the scheduled process receives its secrets.

**Why it diverges:** Different units can schedule in UTC vs local time, double-run after DST or an overlap, silently lose an unattended failure, or run cron with an environment that lacks provider credentials. This is an initiative-owned operational dimension, not implementation detail.

**Disposition: autofix.** Add an operational AD (or explicitly defer a bounded part) that binds supported local environment(s), app-data/config/secret loading for noninteractive cron, IANA timezone and DST behavior, durable cross-process lock ownership, missed-run/retry policy, run status persistence and CLI exit-code/logging contract. State a revisit condition for any intentionally unsupported environment.

### High — Disconnect and user-requested deletion have no owning, atomic boundary

**Evidence:** FR-1 requires local disconnect and OAuth-token removal; FR-10 requires user deletion of saved results and OAuth tokens. AD-4 merely locates tokens and data; AD-8 only age-cleans digests/thread summaries. The capability map calls out “retention and deletion” but names no deletion/disconnect use case or repository/token-store transaction rule.

**Why it diverges:** A builder can delete summaries but leave a refresh token, delete a token but retain account/filter binding, or race cleanup against a new analysis. The advertised privacy control then has inconsistent outcomes.

**Disposition: autofix.** Add an AD binding a single account-data lifecycle service: disconnect and erase operations remove OAuth credentials, account identity/filter/config binding and persisted results according to an explicit scope; they serialize with analysis and return a truthful status. Define whether AI keys are intentionally excluded from “delete account data” and how that is communicated.

### High — Stack entries are not verified, reproducible technology decisions

**Evidence:** Four Stack rows use `current`/`current compatible release`; `uv` delegates exactness to a lockfile not yet part of the structural seed; OpenAI names `2.38.0 or compatible locked update`, whereas the current package release is 2.46.0. The MCP SDK presently recommends v1 for production and has a v2 pre-release, a compatibility fork the spine leaves open.

**Why it diverges:** Two builders can resolve different SDK major versions, FastMCP APIs and OAuth transitive dependencies despite both following the text. A future `uv lock` cannot repair an architecture decision that never picked its compatibility line.

**Disposition: autofix.** Record the review-date and exact compatible constraints (including an MCP v1 upper bound until a deliberate v2 migration), name the FastMCP package/API actually selected, and seed `pyproject.toml` plus committed `uv.lock` as the authoritative reproducibility artefacts. Revalidate before implementation if package versions change.

## Medium findings

### Medium — Gmail filter is not a stable domain/Port contract

**Evidence:** AD-5 says the adapter returns thread-first candidates and saves an Active Gmail Filter; the PRD allows sender, label and keyword filters and requires display of resolved filter and count before save (FR-2). Neither the domain model nor a Port owns the canonical filter representation, validation result, deterministic rendering to Gmail query, or snapshot used by deduplication.

**Why it diverges:** Implementers may store a raw Gmail search string, a typed structured filter, or both; quoted keywords, label semantics and a changed filter's “newly matching” transition will then produce different results and cache behavior.

**Disposition: autofix.** Bind a validated `GmailFilter` value/AST and `FilterPreview` contract in domain/application, with one adapter translation and a persisted canonical form/version. Have AD-3/AD-5 state how filter revision participates in eligibility and run snapshots.

### Medium — The AI output contract does not preserve the PRD’s user-facing meaning

**Evidence:** AD-6 fixes English priorities `high`/`medium`/`low` and an unrestricted `actions` field. FR-4 defines Polish priority semantics, says actions must be concrete or explicitly absent, and prohibits invented deadlines/owners; it also requires a source-thread route and an uncertainty notice. The map places summaries under AD-5/AD-6 but does not bind those fields or validation rules.

**Why it diverges:** Provider adapters can produce valid `ThreadSummary` objects with fabricated owners/dates, an absent-vs-empty action ambiguity, or no source/uncertainty presentation.

**Disposition: autofix.** Expand the validated result contract (or add a presentation/result AD) to bind action representation and prohibition, source-thread locator, uncertainty/disclaimer field, provider-specific status and the product-facing priority vocabulary/mapping.

## What is already convergent

- The selected Ports-and-Adapters paradigm and AD-1 give a useful, enforceable dependency direction.
- AD-2 meaningfully prevents unintended remote/REST and Gmail mutation surfaces for the three MVP tools.
- AD-3, AD-7 and AD-8 cover the core deduplication, result-truthfulness and 30-day retention intent; the gap is their interaction with lifecycle deletion and OS-level execution.
- All PRD areas are represented in the capability map at a coarse level; the findings above identify where that map does not yet translate a capability into a binding, enforceable rule.
- No parent spine or brownfield codebase is declared, so inherited-invariant and code-ratification checks are not applicable.

## Deferred check

The listed Deferred items are appropriately outside the local MVP and have plausible revisit triggers, except that “local `stdio`” does not defer the need to define how the local scheduled process operates. The operational finding above must be decided now; it cannot be left implicit under the remote-hosting deferral.
