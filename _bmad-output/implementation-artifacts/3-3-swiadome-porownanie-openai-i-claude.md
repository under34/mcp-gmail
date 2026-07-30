---
title: 'Story 3.3: Świadome porównanie OpenAI i Claude'
status: done
baseline_commit: 1bf2f85
created: 2026-07-29
---

# Story 3.3: Świadome porównanie OpenAI i Claude

## Story

As a użytkownik budujący demonstrację GenAI,
I want porównać podsumowania OpenAI i Claude dla jednego dozwolonego Wątku,
so that oceniam różnice modeli bez automatycznego mnożenia kosztów lub rozszerzania zakresu danych.

## Acceptance Criteria

1. `compare_summaries` przyjmuje jawny `thread_id` i używa wyłącznie bieżącego Aktywnego Filtru Gmail aktywnego konta. Podgląd sprawdza, czy dokładnie ten Wątek należy do kandydatów filtra; Wątek spoza filtra albo brakujący zwraca kanoniczne `failed`, `data: null`, reason i next action **bez** `fetch_clean_text()` oraz bez wywołania OpenAI/Claude. Nie wolno przyjąć jednorazowego query ani zmieniać Aktywnego Filtru.
2. Pomyślny podgląd zwraca identyfikator Wątku, rozwiązany aktywny filtr, lokalnie ujawniony zestaw dostawców w kanonicznej kolejności `openai`, `claude`, oraz nieprzezroczysty token podglądu. Po jawnej akceptacji token potwierdzenia jest krótkotrwały i jednokrotnego użycia oraz wiąże konto, operację `compare_summaries`, hash aktywnego filtra, dokładnie jedną migawkę `ThreadCandidate`, uporządkowany zestaw obu dostawców i hash jednego oczyszczonego `AnalysisInput`.
3. Brakły, pusty, wygasły, wykorzystany lub niedopasowany token zwraca `failed` z instrukcją odświeżenia podglądu, zanim nastąpi pobranie pełnej treści Gmaila albo jakiekolwiek wywołanie AI. Zmiana konta, Wątku albo oczyszczonego wejścia po potwierdzeniu powoduje bezpieczny błąd bez rozszerzenia zakresu. Token, prompt, body i klucze API nie trafiają do odpowiedzi, logów ani SQLite.
4. Przy ważnym tokenie oba adaptery otrzymują **ten sam** oczyszczony tekst w pamięci, po jednym wywołaniu każdego dostawcy i bez retry/fallbacku. Wynik zawiera dwa niezależne rekordy provider-result z providerem, `status`, opcjonalnym `ThreadSummary` schema v1 oraz bezpiecznym `reason`; każdy poprawny summary ma faktycznego dostawcę `openai` lub `claude`.
5. Status narzędzia jest `complete` tylko gdy obaj dostawcy zwrócą poprawne summary, `partial` gdy dokładnie jeden zwróci poprawny summary, i `failed` gdy żaden nie zwróci poprawnego summary. Awaria jednego dostawcy nie blokuje wywołania drugiego i nie ukrywa przyczyny; wynik nie podstawia podsumowania z drugiego modelu.
6. FastMCP nadal ma dokładnie trzy narzędzia i lokalny transport `stdio`; `compare_summaries` zastępuje placeholder, a `get_daily_digest` i `summarize_gmail` zachowują istniejące zachowanie/envelope. Gdy brakuje klucza któregokolwiek z wymaganych dostawców, tylko porównanie zwraca bezpieczny `failed` z instrukcją konfiguracji — bez body i bez wywołań AI.

## Kontrakt MCP

`compare_summaries(thread_id, preview_token, confirm, confirmation_token)` działa w trzech fazach:

1. **Preview**: tylko `thread_id`; filtr aktywny → metadata kandydatów → sprawdzenie członkostwa → odpowiedź z `phase: "preview"`, `thread_id`, `query`, `providers: ["openai", "claude"]`, tokenem podglądu. Zero body/AI.
2. **Confirm**: `preview_token` i `confirm: true`; po jawnej zgodzie pobiera i oczyszcza wyłącznie jeden Wątek, wylicza hash wejścia i zwraca `phase: "confirmed"` z tokenem wykonania. Zero AI.
3. **Execute**: wyłącznie `confirmation_token`; atomowo konsumuje token, ponownie weryfikuje konto i hash identycznego oczyszczonego tekstu, a następnie niezależnie wywołuje OpenAI i Claude.

Nieobsługiwane kombinacje parametrów, w tym pusty token, są `failed`; nie mogą przejść do fazy preview ani wykonać side effectów. Klient nie przekazuje raw body ani nie wybiera dostawców.

## Tasks / Subtasks

- [x] Dodaj model i persystencję potwierdzenia dla dwóch dostawców. (AC: 2–3)
  - [x] Uogólniono istniejące modele potwierdzeń Story 3.2 bez zmiany kompatybilnych rekordów jednoproviderowych.
  - [x] Kanoniczny provider set `openai,claude`, hash jednej migawki i walidacja SQLite są wiązane z tokenem fail-closed.
  - [x] Zachowano TTL, opaque token, atomowy single-use i istniejące czyszczenie danych konta.
- [x] Dodaj application use case porównania aktywnego filtru. (AC: 1–5)
  - [x] Używany jest wyłącznie Aktywny Filtr Gmail; Wątek poza nim kończy się przed pobraniem body i AI.
  - [x] Obaj dostawcy dostają ten sam zweryfikowany oczyszczony tekst w pamięci.
  - [x] Wywołania są niezależne, jednokrotne i walidują provider, konto, Wątek oraz schema v1.
  - [x] Dedykowana agregacja zwraca uczciwe `complete` / `partial` / `failed`, bez retry ani fallbacku.
- [x] Skomponuj oba dostawcy wyłącznie dla porównania i podłącz FastMCP. (AC: 4–6)
  - [x] Factory tworzy jawnie adaptery OpenAI i Claude wyłącznie przy obu kluczach; `AI_PROVIDER` nie wybiera porównania.
  - [x] `compare_summaries` obsługuje ścisłe trzy fazy w ramach nadal trzech narzędzi FastMCP/stdio.
  - [x] Niepełna konfiguracja bezpiecznie wyłącza tylko porównanie, zachowując Digest i `summarize_gmail`.
- [x] Dodaj testy unit/adapter i pełną regresję. (AC: 1–6)
  - [x] Pokryto odmowę Wątku spoza filtra, brakły/replay token i zmienione wejście bez wywołań AI.
  - [x] Pokryto identyczne wejście, jednokrotne wywołania, `partial` i `failed` dla awarii providerów.
  - [x] Pokryto routing FastMCP, dokładnie trzy narzędzia oraz wymóg obu kluczy.
  - [x] Uruchomiono `uv run pytest -q` oraz `uv run ruff check src tests`.

### Review Findings

- [x] [Review][Patch] Revalidate the current Active Filter before body access [src/gmail_mcp/application/confirmed_comparison.py:115] — fixed: confirmation and execution now reject a changed active filter before body access (AC 1–3).
- [x] [Review][Patch] Preserve both provider results when neither provider succeeds [src/gmail_mcp/application/confirmed_comparison.py:195] — fixed: terminal failure retains both safe provider-result records (AC 4–5).
- [x] [Review][Patch] Return a safe, distinct provider-failure reason [src/gmail_mcp/application/confirmed_comparison.py:208] — fixed: configuration, request, and invalid-summary failures have distinct sanitized reasons (AC 4–5).
- [x] [Review][Patch] Reject an empty preview token before phase routing [src/gmail_mcp/adapters/fastmcp_server.py:80] — fixed: empty preview tokens fail before routing or side effects (MCP contract).
- [x] [Review][Patch] Revalidate current candidate membership before body access [src/gmail_mcp/application/confirmed_comparison.py:128] — fixed: confirmation and execution rediscover the candidate under the unchanged active filter before body access (AC 1 and AC 3).
- [x] [Review][Patch] Keep malformed provider output inside per-provider isolation [src/gmail_mcp/application/confirmed_comparison.py:236] — fixed: validation and serialization failures become an invalid-summary result and do not block the other provider (AC 4–5).
- [x] [Review][Patch] Blokuj zapisywanie i konsumpcję potwierdzeń podczas aktywnej bramki usuwania konta [src/gmail_mcp/adapters/sqlite_confirmation.py:84] — poprawiono: porównanie nie może utworzyć ani zużyć tokenu w czasie usuwania danych konta.
- [x] [Review][Patch] Ponownie potwierdź członkostwo Wątku w Aktywnym Filtrze po pobraniu body, przed wywołaniem dostawców [src/gmail_mcp/application/confirmed_comparison.py:176] — poprawiono: zmiana filtra lub przynależności kończy wykonanie przed wywołaniami AI.
- [x] [Review][Decision] Ustal semantykę usuwania danych wobec potwierdzonego wykonania będącego już w toku — rozstrzygnięto: usuwanie blokuje nowe operacje i czeka na zwolnienie lease przez trwające wykonanie przed czyszczeniem danych.
- [x] [Review][Patch] Dodaj lease aktywnego wykonania konta, które blokuje rozpoczęcie usuwania do czasu zakończenia pobrania body i porównania [src/gmail_mcp/application/confirmed_comparison.py:160] — poprawiono: bramka czeka na lease, a wykonanie nabywa go przed odczytem body i zwalnia po porównaniu.
- [x] [Review][Patch] Traktuj klucze API z samymi białymi znakami jako brak konfiguracji porównania [src/gmail_mcp/bootstrap/summary_provider.py:22] — poprawiono: oba klucze są walidowane po `strip()` przed utworzeniem dostawców.
- [x] [Review][Decision] Ustal limit oczekiwania na aktywny lease podczas usuwania danych — rozstrzygnięto: maksymalnie 60 sekund, następnie bezpieczny błąd z instrukcją ponowienia usuwania.
- [x] [Review][Patch] Zakończ usuwanie bezpiecznym błędem po 60 sekundach oczekiwania na lease [src/gmail_mcp/adapters/sqlite_analysis_state.py:303] — poprawiono: bramka jest odnawiana podczas oczekiwania, a limit zwraca bezpieczny błąd.
- [x] [Review][Patch] Obejmij lease także fazę potwierdzenia przed pobraniem body [src/gmail_mcp/application/confirmed_comparison.py:119] — poprawiono: lease obejmuje pobranie body i zapis tokenu potwierdzenia.
- [x] [Review][Patch] Odnawiaj bramkę usuwania podczas oczekiwania na lease [src/gmail_mcp/adapters/sqlite_analysis_state.py:303] — poprawiono: bramka jest odnawiana podczas oczekiwania na aktywne wykonanie.

## Dev Notes

### Guardrails architektoniczne

- `compare_summaries` jest ograniczone przez **Aktywny** Filtr Gmail, nie przez query jednorazowy. Wątek poza filtrem kończy się przed body i AI. [Source: `ARCHITECTURE-SPINE.md#AD-5`, `epics.md#Story 3.3`]
- Potwierdzenie wiąże operation, konto, filter hash, dokładnie jeden Wątek, oba providery i hash oczyszczonego wejścia. Oba modele otrzymują identyczną migawkę; token jest single-use. [Source: `ARCHITECTURE-SPINE.md#AD-9`]
- Provider errors są widoczne niezależnie; OpenAI/Claude nie są fallbackiem dla siebie. `ThreadSummary` schema v1 pozostaje wspólnym kontraktem. [Source: `ARCHITECTURE-SPINE.md#AD-6`]
- Domain/application nie importują SDK. FastMCP jest stdio-only, bootstrap to jedyny composition root, a tylko application mutuje SQLite. [Source: `ARCHITECTURE-SPINE.md#AD-1`, `#AD-2`, `#AD-3`]
- Pełny body, prompt i sekret nie mogą trafić do trwałego stanu/logów. Przy czyszczeniu konta muszą zostać usunięte także comparison confirmations. [Source: `ARCHITECTURE-SPINE.md#AD-4`, `#AD-8`, `#AD-10`]

### Reuse i ograniczenia istniejącego kodu

- Reużyj wzorzec trzech faz z `application/confirmed_analysis.py`, `domain/confirmation.py` i `SqliteConfirmationAdapter`, ale nie mieszaj tokenu `summarize_gmail` z `compare_summaries`.
- `GmailOAuthAdapter.find_thread_candidates()` pobiera metadata, a `fetch_clean_text()` zapewnia fingerprint konta, `latest_message_id`, brak załączników i sanitizację. Nie implementuj nowego odczytu body.
- `SummarizeAnalysisRun` zapisuje wynik jednego providera dla Wątku i agreguje per Wątek; dla porównania potrzebna jest dedykowana agregacja per provider.
- `create_summary_provider(settings)` intencjonalnie tworzy jednego wybranego providera. Porównanie potrzebuje nowej jawnej factory obu adapterów i bezpiecznej niedostępności przy brakującym kluczu.
- `SqliteAnalysisStateAdapter.delete_account_data()` oraz `local_account_fingerprints()` już obejmują `analysis_confirmation`; nie omijaj tych poprawek z review Story 3.2.

### Project Structure Notes

- Przewidywane nowe moduły: `src/gmail_mcp/application/confirmed_comparison.py`; ewentualne rozszerzenia `domain/confirmation.py` i `adapters/sqlite_confirmation.py` muszą być kompatybilne z recordami 3.2.
- Przewidywane aktualizacje: `adapters/fastmcp_server.py`, `bootstrap/mcp.py`, `bootstrap/summary_provider.py` oraz testy comparison/SQLite/FastMCP/bootstrap.
- Nie dodawaj zależności. Projekt używa Python 3.12, `mcp>=1.27,<2`, OpenAI `2.38.0`, Anthropic `0.117.0` i istniejącego `uv.lock`. [Source: `pyproject.toml`, `ARCHITECTURE-SPINE.md#AD-11`]

### Wnioski z Story 3.2 i review

- Token musi być nieprzezroczysty, odporny na replay i zweryfikowany przed body/AI; pusty token jest błędem, nie sygnałem nowego preview.
- Nie raportuj `complete`, gdy claim odjął część zatwierdzonej migawki.
- Persisted snapshot wymaga niezależnego hasha oraz walidacji przed konsumpcją.
- Usunięcie danych konta unieważnia wszystkie potwierdzenia tego konta.

## References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.3`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#FR-8`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#FR-9`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-6`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]
- [Source: `_bmad-output/implementation-artifacts/3-2-potwierdzona-analiza-ad-hoc-przez-wybranego-dostawce.md`]

## Dev Agent Record

### Completion Notes

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Dodano trzyfazowe, potwierdzane porównanie jednego Wątku ograniczonego Aktywnym Filtrem Gmail.
- Token wiąże konto, operację, filtr, pojedynczą migawkę, obu providerów i hash oczyszczonego wejścia.
- Pełna walidacja: `123 passed`; `uv run ruff check src tests` bez błędów.

### File List

- _bmad-output/implementation-artifacts/3-3-swiadome-porownanie-openai-i-claude.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/gmail_mcp/application/confirmed_comparison.py
- src/gmail_mcp/adapters/fastmcp_server.py
- src/gmail_mcp/bootstrap/mcp.py
- src/gmail_mcp/bootstrap/summary_provider.py
- tests/unit/test_confirmed_comparison.py
- tests/unit/test_fastmcp_server.py
- tests/unit/test_summary_provider.py

## Change Log

- 2026-07-29: Utworzono Story 3.3 z potwierdzonym porównaniem dwóch providerów i niezależnymi statusami wyników.
- 2026-07-29: Zaimplementowano porównanie OpenAI i Claude; Story gotowe do review.
