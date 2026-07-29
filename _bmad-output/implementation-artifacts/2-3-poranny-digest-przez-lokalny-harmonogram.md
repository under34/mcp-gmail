---
title: 'Story 2.3: Poranny Digest przez lokalny Harmonogram'
status: done
baseline_commit: 7ae1816e88e2633f6421841c7b7e466ab36107a9
created: 2026-07-29
---

# Story 2.3: Poranny Digest przez lokalny Harmonogram

## Story

As a właściciel konta Gmail,
I want otrzymywać lokalnie wygenerowany poranny Digest,
so that rozpoczynam dzień od najważniejszych nowych Wątków i działań.

## Acceptance Criteria

1. Lokalny cron wywołuje polecenie CLI o domyślnej godzinie 08:00 czasu lokalnego; użytkownik może zmienić godzinę albo wyłączyć Harmonogram w lokalnej konfiguracji. Ręczne wykonanie i cron uruchamiają ten sam use case.
2. Udane wykonanie zapisuje Digest ze statusem `complete` albo `partial`, czasem UTC utworzenia, zakresem `AnalysisRun`, liczbą zakwalifikowanych Wątków oraz uporządkowanymi pozycjami: `ThreadSummary`, `thread_id`/link i deterministycznym powodem uwzględnienia.
3. Błąd OAuth, Gmail API, wybranego dostawcy, konfiguracji albo uruchomienia harmonogramu zapisuje najnowszy Digest jako `failed` albo `partial` z bezpiecznym `reason` i `next_action`; nie loguje sekretów ani treści. Nie stosuje fallbacku dostawcy.
4. Każde uruchomienie odczytuje konfigurację i tworzy dostawcę przed planowaniem; zmiany harmonogramu lub dostawcy dotyczą dopiero kolejnego uruchomienia. Równoległe ręczne/cronowe wykonania wykorzystują istniejące claims per konto i nie duplikują analizy.

## Tasks / Subtasks

- [x] Zdefiniuj w `domain/digest.py` niezmienne `Digest`, `DigestItem` i dozwolone statusy/powody uwzględnienia; pozycje zawierają wyłącznie metadane oraz istniejący `ThreadSummary`, nigdy body/prompt/załączniki. (AC 2–3)
- [x] Dodaj `application/digest.py`: port repozytorium Digestu i jeden use case `RunDailyDigest`, który komponuje `PlanActiveFilterAnalysis` → `SummarizeAnalysisRun` → zapis Digestu; obsłuż zero kandydatów, complete, partial i bezpieczny failed. (AC 1–4)
- [x] Rozszerz `SqliteAnalysisStateAdapter` o trwałe tabele/operacje Digestu, atomowy zapis ostatniego wyniku oraz odczyt metadanych pod przyszłe `get_daily_digest`; zachowaj `BEGIN IMMEDIATE`, namespace konta i brak treści wiadomości. (AC 2–4)
- [x] Rozszerz `Settings` o walidowaną lokalną konfigurację harmonogramu (`DIGEST_SCHEDULE_ENABLED`, `DIGEST_SCHEDULE_TIME`, opcjonalna strefa IANA), domyślnie enabled/`08:00`; nie dodawaj zależności ani nie mutuj systemowego crontaba. (AC 1, 4)
- [x] Dodaj do `bootstrap/cli.py` cron-friendly `run-daily-digest` oraz ręczny entry point korzystające z identycznej kompozycji bootstrapu: Gmail adapter, aktywny filtr, SQLite, wybrany provider i `FinishAnalysis`. Polecenie zwraca bezpieczny status oraz kod niezerowy dla `failed`; dokumentacja podaje przykładową linię crona uruchamiającą CLI. (AC 1, 3–4)
- [x] Dodaj testy domain/application/SQLite/bootstrap bez Gmaila, kluczy i sieci: domyślne/zmienione/wyłączone ustawienia, ten sam flow ręczny i cron, digest zero/complete/partial/failed, bezpieczne reason/next_action, snapshot dostawcy, deduplikacja równoległa oraz brak treści w SQLite/logach. (AC 1–4)

## Dev Notes

- Reużyj bez zmian `PlanActiveFilterAnalysis` (`application/analysis_state.py`) do pobrania Aktywnego Filtru i atomowego claimu oraz `SummarizeAnalysisRun` (`application/thread_summary.py`) do przetwarzania wyłącznie migawki. Nie twórz osobnej ścieżki Gmail/AI dla crona.
- `bootstrap` jest jedynym composition rootem: zbuduj `GmailOAuthAdapter`, `ActiveFilterRepositoryAdapter`, pojedynczy `SqliteAnalysisStateAdapter(settings.paths.sqlite)`, `FinishAnalysis` i `create_summary_provider(load_settings())`. Dla jednego runu settings/provider są snapshotem.
- Cron systemu operacyjnego wywołuje CLI; aplikacja nie instaluje ani nie edytuje crontaba. Nie wprowadzaj FastMCP, tokenu potwierdzenia, retencji ani porównania modeli — należą do Stories 2.4 i 3.x.
- Istniejący stan ma 15-minutowy lease, snapshot uporządkowanych kandydatów i ochronę przed nadpisaniem runu terminalnego. Digest zapisuj także dla zero kandydatów i błędów przed planem, aby „ostatni” wynik był prawdziwy.
- `ThreadCandidate` nie zawiera powodu uwzględnienia. Dodaj deterministyczne, trwałe provenance w warstwie planowania/repozytorium (`new_message`, `newly_matching`, `reanalysis`); nie zgaduj go z tekstu czy odpowiedzi AI.
- Wszystkie statusy użytkownika są `complete`/`partial`/`failed`; `partial`/`failed` wymagają krótkiego safe reason i `next_action` (np. reconnect Gmail, configure selected provider, retry later). Żaden błąd nie może zawierać body, promptu, tokenu ani klucza.
- Zachowaj hexagonalność: domain/application bez SDK i `sqlite3`; porty w `application`, SQLite/Gmail/CLI w adapterach/bootstrap. Stosuj `tmp_path`, fake porty i sanitizowane fixtures; `uv run pytest -q`, `uv run ruff check .`.

### Project Structure Notes

- Nowe: `src/gmail_mcp/domain/digest.py`, `src/gmail_mcp/application/digest.py`, testy unit Digestu.
- Aktualizuj: `src/gmail_mcp/adapters/sqlite_analysis_state.py`, `src/gmail_mcp/bootstrap/settings.py`, `src/gmail_mcp/bootstrap/cli.py`, README oraz przyległe testy bootstrapu/SQLite.
- `AppPaths.digests` istnieje, lecz SQLite jest źródłem prawdy dla Digestu i przyszłego MCP odczytu; nie twórz równoległego plikowego magazynu.

### References

- `_bmad-output/planning-artifacts/epics.md`, Story 2.3; FR-3 i FR-5.
- `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md`, FR-3–5 oraz NFR-1–5.
- `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md`, AD-3–8, AD-10 oraz Scheduler = OS cron → CLI.
- `_bmad-output/implementation-artifacts/2-1-lokalny-stan-analizy-i-deduplikacja-watkow.md` i `2-2-walidowane-podsumowanie-watku-przez-wybranego-dostawce-ai.md`.

## Dev Agent Record

### Completion Notes

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Dodano Digest, trwałe metadane SQLite, ustawienia harmonogramu oraz cron-friendly CLI bez utrwalania treści Gmaila.
- Zweryfikowano bezpieczne błędy i podstawowy flow CLI; `92 passed`, Ruff czysty.
- Dodano scenariusz `partial` i snapshot dostawcy; pełna regresja: `93 passed`, Ruff czysty.

### File List

- README.md
- src/gmail_mcp/domain/digest.py
- src/gmail_mcp/application/digest.py
- src/gmail_mcp/adapters/sqlite_analysis_state.py
- src/gmail_mcp/bootstrap/settings.py
- src/gmail_mcp/bootstrap/cli.py
- tests/unit/test_digest.py
- tests/unit/test_digest_runner.py
- tests/unit/test_sqlite_analysis_state.py
- tests/unit/test_bootstrap.py
- tests/unit/test_gmail_connection.py

## Change Log

- 2026-07-29: Zaimplementowano lokalny Digest, harmonogram konfiguracji, SQLite i CLI; status ready for review.
- 2026-07-29: Utworzono Story 2.3 z kontekstem harmonogramu, Digestu, istniejących claims i granic prywatności.

### Review Findings

- [x] [Review][Patch] Trwale wyprowadzaj i zapisuj rzeczywisty powód uwzględnienia pozycji Digestu [src/gmail_mcp/application/digest.py:55]
- [x] [Review][Patch] Egzekwuj konfigurację czasu i strefy harmonogramu w uruchomieniu `--scheduled` [src/gmail_mcp/bootstrap/cli.py:41]
- [x] [Review][Patch] Pozostaw ręczne uruchomienie Digestu dostępne po wyłączeniu harmonogramu [src/gmail_mcp/bootstrap/cli.py:43]
- [x] [Review][Patch] Zapisuj bezpieczny Digest failed również dla błędów konfiguracji i dostawcy [src/gmail_mcp/bootstrap/cli.py:43]
- [x] [Review][Patch] Waliduj dokładny format `HH:MM` dla czasu harmonogramu [src/gmail_mcp/bootstrap/settings.py:180]
- [x] [Review][Patch] Zapisuj failed Digest, gdy odczyt podsumowań z repozytorium się nie powiedzie [src/gmail_mcp/application/digest.py:45]
- [x] [Review][Patch] Odczyt ostatniego Digestu ogranicz do fingerprintu aktywnego konta [src/gmail_mcp/adapters/sqlite_analysis_state.py:134]
