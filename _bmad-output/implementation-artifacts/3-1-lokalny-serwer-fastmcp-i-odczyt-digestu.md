---
title: 'Story 3.1: Lokalny serwer FastMCP i odczyt Digestu'
status: done
baseline_commit: a45a17c
created: 2026-07-29
---

# Story 3.1: Lokalny serwer FastMCP i odczyt Digestu

## Story

As a użytkownik klienta MCP,
I want lokalnie odkryć serwer Gmail MCP i pobrać ostatni Digest,
so that wykorzystuję wyniki analizy bez wystawiania usługi do sieci.

## Acceptance Criteria

1. Serwer działa wyłącznie przez `stdio` i klient odkrywa dokładnie trzy narzędzia: `get_daily_digest`, `summarize_gmail`, `compare_summaries`. Dwa ostatnie są na tym etapie bezpiecznymi placeholderami zgodnymi z envelope i nie pobierają Gmaila ani nie wywołują AI.
2. Każde narzędzie zwraca dokładnie `{"status": "complete|partial|failed", "data": object|null, "reason": string|null, "next_action": string|null}`. Dla `complete` reason/next_action są `null`; dla `partial`/`failed` są niepuste. `get_daily_digest` zwraca ostatni Digest aktywnego konta: zakres, czas, liczbę, dostawcę oraz uporządkowane pozycje (`thread_id`, link, summary, priority, actions, provider, inclusion_reason, disclaimer).
3. Gdy OAuth jest niedostępny, narzędzie zwraca `failed` z `data: null` i nie odczytuje Digestu. Przy działającym OAuth snapshot fingerprintu jest ponownie sprawdzany przed odczytem; co najmniej dwa konta w testach dowodzą izolacji. Brak Digestu albo ostatni `failed`/`partial` zwraca bezpieczny status z reason i next_action, bez tracebacku, tokenu, e-maila, body ani promptu.
4. Nie powstaje endpoint HTTP/SSE, narzędzie nie zmienia Gmaila i bootstrap pozostaje jedynym miejscem kompozycji SDK/adapters.

## Tasks / Subtasks

- [x] Dodaj domain/application use case odczytu Digestu i serializację MCP envelope bez importów SDK/SQLite. (AC 2–3)
  - [x] Rozszerz port stanu o odczyt ostatniego Digestu dla fingerprintu aktywnego konta; nie zwracaj danych innego konta.
  - [x] Odtwórz uporządkowane `DigestItem` z `digest_item` i `thread_summary`; brak podsumowania traktuj jako bezpieczny częściowy/błędny wynik, nigdy jako sfabrykowaną pozycję.
  - [x] Łącz po `(run_id, thread_id, account)`; osierocona/nieprawidłowa pozycja lub niespójny count zwraca `partial` z zachowanymi poprawnymi pozycjami i next_action, a brak bezpiecznej rekonstrukcji zwraca `failed`.
  - [x] Zmapuj `Digest`/`DigestItem` do danych JSON-serializowalnych bez dodatkowych treści Gmaila.
- [x] Dodaj adapter FastMCP i entry point `stdio`. (AC 1, 4)
  - [x] Użyj zablokowanego SDK `mcp>=1.27,<2` i importu `mcp.server.fastmcp.FastMCP`; nie dodawaj zależności.
  - [x] Zarejestruj wyłącznie trzy nazwane tools; placeholdery Story 3.2/3.3 zwracają `failed`, `data: null` i stabilny reason/next_action bez side effectów.
  - [x] Dodaj jeden skrypt `gmail-mcp-server` uruchamiający stdio bez hosta, portu lub HTTP; stdout jest wyłącznie dla protokołu MCP, a diagnostyka trafia na stderr.
- [x] Skomponuj adaptery w bootstrapie i obsłuż błędy lokalnie. (AC 2–4)
  - [x] Ustal fingerprint przez istniejący `GmailOAuthAdapter.current_account_email()`; nie ujawniaj e-maila przy błędzie.
  - [x] Reużyj `SqliteAnalysisStateAdapter.latest_digest(account)` i istniejących `Digest`/`ThreadSummary`; nie twórz nowego store’u.
- [x] Dodaj testy in-memory/FastMCP bez sieci, tokenów i Gmaila. (AC 1–4)
  - [x] Sprawdź discoverability dokładnie trzech tools przez subprocess entry point, stdout-only MCP, sukces get_daily_digest, brak Digestu, partial/failed, izolację dwóch kont oraz brak naruszeń prywatności.
  - [x] Uruchom `uv run pytest -q` oraz `uv run ruff check .`.

## Dev Notes

- Architektura wymaga FastMCP wyłącznie lokalnie przez stdio; nie dodawaj HTTP/SSE ani tooli zapisu Gmaila. [Source: `ARCHITECTURE-SPINE.md#AD-2`]
- `bootstrap/cli.py` jest obecnym composition rootem, `SqliteAnalysisStateAdapter.latest_digest(account_fingerprint)` już ogranicza odczyt do konta, a `domain/digest.py` definiuje status/reason/next action. Rozszerz je zamiast duplikować kontrakty.
- Obecne `latest_digest()` odtwarza wyłącznie metadane i `items=()`: Story 3.1 musi dołączyć pozycje według `digest_item.position`, z rzeczywistym `summary.provider`, linkiem oraz `inclusion_reason`. Nie pokazuj syntetycznego Digestu konfiguracji z fingerprintem `""` dla aktywnego konta.
- Dane i sekrety pozostają lokalne; domain/application nie importują SDK ani `sqlite3`. Wszystkie błędy adapterów mapuj na bezpieczny envelope. [Source: `ARCHITECTURE-SPINE.md#AD-1`, `#AD-4`, `#AD-7`]
- SDK v1 jest przypięte w `pyproject.toml`/`uv.lock` do `mcp 1.28.1`. Oficjalny SDK używa `from mcp.server.fastmcp import FastMCP`, a stdio jest obsługiwanym transportem. [MCP Python SDK](https://py.sdk.modelcontextprotocol.io/)
- Story 2.4 dodała retencję i czyszczenie; MCP jest wyłącznie odczytowy i nie omija bramek stanu ani lokalnych granic konta.

### Project Structure Notes

- Nowe (przewidywane): `src/gmail_mcp/application/digest_read.py`, `src/gmail_mcp/adapters/mcp_server.py`, `src/gmail_mcp/bootstrap/mcp.py`, testy MCP.
- Aktualizuj tylko niezbędne porty/adapters oraz README z instrukcją uruchomienia stdio.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.1`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#FR-6`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-2`]
- [Source: `_bmad-output/implementation-artifacts/2-4-retencja-i-reczne-usuwanie-lokalnych-danych.md`]

## Dev Agent Record

### Completion Notes

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Zaimplementowano odczyt Digestu, adapter FastMCP z trzema tools oraz entry point stdio.
- Pełna regresja: 105 passed; Ruff czysty.

### File List

- _bmad-output/implementation-artifacts/3-1-lokalny-serwer-fastmcp-i-odczyt-digestu.md
- README.md
- pyproject.toml
- src/gmail_mcp/application/digest_read.py
- src/gmail_mcp/adapters/fastmcp_server.py
- src/gmail_mcp/adapters/sqlite_analysis_state.py
- src/gmail_mcp/bootstrap/mcp.py
- tests/unit/test_digest_read.py
- tests/unit/test_fastmcp_server.py

## Change Log

- 2026-07-29: Utworzono Story 3.1 z kontraktem stdio, trzema narzędziami MCP i odczytem lokalnego Digestu.
- 2026-07-29: Zaimplementowano lokalny serwer FastMCP i odczyt Digestu; status review.

### Review Findings

- [x] [Review][Patch] Zdefiniuj jeden kanoniczny JSON envelope, w tym `next_action`, typy pól i semantykę null dla każdego statusu.
- [x] [Review][Patch] Doprecyzuj bezpieczne zachowanie przy niedostępnym OAuth i izolację co najmniej dwóch kont bez odczytu niepowiązanego Digestu.
- [x] [Review][Patch] Ustal deterministyczną politykę dla osieroconych/uszkodzonych pozycji Digestu i niespójnych liczników.
- [x] [Review][Patch] Wymagaj dla placeholderów statusu `failed`, `data: null`, bezpiecznego reason i next_action bez side effectów.
- [x] [Review][Patch] Ustal jeden entry point stdio, stdout zarezerwowany dla MCP, stderr dla diagnostyki i test subprocess discovery.
- [x] [Review][Patch] Zwracaj `partial` zamiast `complete`, gdy rekonstrukcja pomija osierocone pozycje lub licznik Digestu nie zgadza się z pozycjami [src/gmail_mcp/adapters/sqlite_analysis_state.py:156]
- [x] [Review][Patch] Ponownie zweryfikuj fingerprint aktywnego konta przed odczytem Digestu, aby nie zwrócić danych po zmianie OAuth [src/gmail_mcp/bootstrap/mcp.py:15]
- [x] [Review][Patch] Dodaj testy SQLite hydratacji i integrity Digestu oraz test entry point/subprocess stdio wymagane przez AC [tests/unit/test_sqlite_analysis_state.py:106]
