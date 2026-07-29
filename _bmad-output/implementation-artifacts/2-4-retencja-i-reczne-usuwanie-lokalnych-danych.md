---
title: 'Story 2.4: Retencja i ręczne usuwanie lokalnych danych'
status: done
baseline_commit: afe4aab
created: 2026-07-29
---

# Story 2.4: Retencja i ręczne usuwanie lokalnych danych

## Story

As a właściciel danych,
I want automatycznie usuwać stare wyniki i móc ręcznie wyczyścić lokalny stan,
so that ograniczam ryzyko prywatności bez dotykania poczty w Gmailu.

## Acceptance Criteria

1. Czyszczenie retencji usuwa wyłącznie lokalne `Digesty`, ich pozycje oraz `ThreadSummary` starsze niż dokładnie 30 dni, licząc od czasu UTC uruchomienia. Dane równe granicy 30 dni pozostają. Operacja nie zmienia wiadomości, etykiet, filtrów ani innych danych Gmaila.
2. Retencja uruchamia się przed każdym rzeczywistym ręcznym lub harmonogramowym `run-daily-digest`; dostępne jest też lokalne polecenie CLI do jej samodzielnego wywołania. Wynik ujawnia tylko bezpieczny status i techniczne liczniki usuniętych wyników.
3. Ręczne polecenie usunięcia wymaga jawnego `--confirm`. Dla aktywnego konta najpierw trwale blokuje nowe planowanie, bezpiecznie terminalizuje aktywne runy i zwalnia ich claims, a następnie idempotentnie usuwa wskazane lokalne wyniki: Digesty, pozycje Digestu, Podsumowania, runy, stan deduplikacji i członkostwo filtrów. Następna analiza wymaga zwykłego dostępu do Gmaila i ponownie przechodzi deduplikację od czystego stanu.
4. Opcja `--include-oauth-token` usuwa wyłącznie lokalny token OAuth po ustawieniu bramki usuwania; nie usuwa `credentials.json`, kluczy AI, konfiguracji filtra ani niczego w Gmailu/Google. Brak tokenu jest sukcesem idempotentnym. Niebezpieczna ścieżka tokenu lub błąd usunięcia daje bezpieczny `partial`/`failed` z następnym działaniem.
5. Równoległy cron, ręczny Digest i usuwanie nie mogą wskrzesić danych po rozpoczęciu usuwania. Blokada jest trwała per fingerprint konta i jest sprawdzana w repozytorium w tej samej transakcji co planowanie; restart procesu nie może pozostawić konta trwale zablokowanego.
6. Żaden komunikat, log, test fixture ani trwały rekord dodany przez tę historię nie zawiera treści Wątku, załączników, tokenu OAuth, klucza AI, adresu e-mail ani ścieżki sekretu.

## Tasks / Subtasks

- [x] Dodaj domain/application kontrakt bez zależności od `sqlite3` dla wyników retencji i usuwania: status `complete`/`partial`/`failed`, bezpieczny reason/next action i wyłącznie liczniki techniczne. (AC: 1–4, 6)
  - [x] Zdefiniuj port lokalnego stanu oraz use case’y `PurgeExpiredResults` i `DeleteLocalData`.
  - [x] Ustal jeden zegar wejściowy UTC (`now`) dla granicy retencji, aby testy i SQL były deterministyczne.
- [x] Rozszerz `SqliteAnalysisStateAdapter` o atomową retencję i protokół lifecycle usuwania per konto. (AC: 1, 3, 5)
  - [x] W jednej transakcji `BEGIN IMMEDIATE` usuń najpierw `digest_item`, potem odpowiadające `digest`, a niezależnie `thread_summary`, wyłącznie dla rekordów starszych niż `now - 30 dni`.
  - [x] Zachowaj `thread_state`, `filter_membership`, `analysis_run` i claims podczas samej retencji — są potrzebne do deduplikacji.
  - [x] Dodaj trwałą, odzyskiwalną bramkę usuwania per konto. `plan()` sprawdza ją pod `BEGIN IMMEDIATE` i nie tworzy nowego runu, gdy usuwanie trwa.
  - [x] Przed pełnym purge oznacz aktywne runy jako terminalne `failed`, oznacz kandydatów jako failed i usuń claims. Następnie usuń dane wyłącznie tego konta, w kolejności zależności: candidates/claims, summaries i digest items/digests, runs, `thread_state`, `filter_membership`.
  - [x] Nie dodawaj szerokiego `rm -rf`, nie usuwaj katalogu danych ani nie kasuj `paths.filters`.
- [x] Użyj istniejącego bezpiecznego `GmailOAuthAdapter.disconnect()` jako portu usunięcia tokenu. (AC: 4–6)
  - [x] Token kasuj wyłącznie po uruchomieniu bramki SQLite; `missing_ok` pozostaje sukcesem.
  - [x] Gdy purge SQLite się powiedzie, ale token nie może zostać usunięty, zwróć bezpieczny status częściowy bez ujawniania ścieżki/tokenu.
- [x] Rozszerz bootstrap i CLI bez mutowania Gmaila. (AC: 2–4, 6)
  - [x] Wywołaj retencję przed rzeczywistym wykonaniem `run-daily-digest`; nie uruchamiaj jej dla `--scheduled` wyłączonego lub „not due”.
  - [x] Dodaj `cleanup-local-data` do ręcznego uruchomienia retencji oraz `delete-local-data --confirm [--include-oauth-token]` do destrukcyjnego purge.
  - [x] Waliduj `--confirm` przed budową adapterów i przed każdym I/O. Wypisuj tylko status, liczniki i bezpieczny reason/next action; `failed` zwraca kod niezerowy.
  - [x] Zaktualizuj README: 30-dniowa retencja, komendy, zakres usuwania i jednoznaczny zakaz modyfikacji Gmaila.
- [x] Dodaj testy bez sieci, kluczy i prawdziwego tokenu. (AC: 1–6)
  - [x] SQLite: granice <30 dni i =30 dni, kolejność `digest_item` → `digest`, izolacja kont, idempotencja, zachowanie deduplikacji po retencji oraz pełne wyczyszczenie po ręcznym purge.
  - [x] Współbieżność: usuwanie terminalizuje aktywny run; późniejsze `save()`/`finish()` nie odtwarzają wyników, a nowe `plan()` jest odrzucone podczas bramki.
  - [x] Application/CLI: automatyczny hook przed Digestem, wymagane `--confirm`, opcjonalny token, bezpieczne `partial`/`failed`, kody wyjścia i brak danych wrażliwych w wyjściu.
  - [x] Uruchom `uv run pytest -q` i `uv run ruff check .`.

## Dev Notes

- Zachowaj heksagonalność: domain/application nie importują `sqlite3`, Gmail SDK ani `Path`; porty definiuj w `application/`, implementacje w adapterach, a kompozycję wyłącznie w `bootstrap/`.
- Rozszerz istniejący `SqliteAnalysisStateAdapter` zamiast tworzyć drugi magazyn. Obecne tabele to `thread_summary(created_at)`, `digest(generated_at)`, `digest_item`, `analysis_run`, `analysis_run_candidate`, `analysis_claim`, `thread_state` i `filter_membership`. Nie mają kluczy obcych, dlatego kolejność kasowania i transakcje są obowiązkowe.
- Obecne `PlanAnalysis._locks` są tylko pamięciowe. Nie są wystarczające dla crona/ręcznych procesów; decyzja o bramce musi zostać podjęta przez SQLite w `BEGIN IMMEDIATE`. Bramka musi mieć bezpieczne odzyskanie po przerwaniu procesu, np. lease/timestamp obsługiwany przez repozytorium.
- `save()` już wymaga runu `running` i aktywnego claimu, a `finish()` nie nadpisuje terminalnego runu. Wykorzystaj te gwarancje: najpierw terminalizuj run i usuń claim, dopiero później kasuj dane. Worker może mieć treść wyłącznie przejściowo w RAM, ale nie może jej ponownie zapisać.
- Ręczny purge czyści stan deduplikacji danego konta (`thread_state`, `filter_membership`) — inaczej kolejna analiza nie przechodziłaby normalnej deduplikacji od zera. Z kolei automatyczna retencja nie usuwa tych tabel.
- `GmailOAuthAdapter.disconnect()` jest idempotentny i odporny na symlink. Nie usuwaj pliku credentials ani nie wywołuj Google revoke; Gmail pozostaje wyłącznie odczytowy.
- `AppPaths.digests` nie jest źródłem prawdy dla Story 2.3. Nie twórz ani nie kasuj równoległego plikowego store’u, nie usuwaj rekursywnie `AppPaths.root`.
- Wzorce testów: `tmp_path`, fake porty, czasy UTC ISO-8601 i sanitizowane fixtures. Do testów granicznych wstrzykuj `now`, nie mockuj globalnego zegara.

### Project Structure Notes

- Nowe (przewidywane): `src/gmail_mcp/application/local_data.py`, `src/gmail_mcp/domain/local_data.py`, testy application retencji/usuwania.
- Aktualizuj: `src/gmail_mcp/adapters/sqlite_analysis_state.py`, `src/gmail_mcp/application/analysis_state.py`, `src/gmail_mcp/bootstrap/cli.py`, `README.md`, `tests/unit/test_sqlite_analysis_state.py`, `tests/unit/test_bootstrap.py`, `tests/unit/test_gmail_connection.py`.
- Nie modyfikuj adapterów dostawców AI, Gmail API ani schematu `ThreadSummary` poza niezbędnymi portami lifecycle.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.4: Retencja i ręczne usuwanie lokalnych danych`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#FR-10: Minimalna retencja danych`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-3`, `#AD-4`, `#AD-8`, `#AD-10`]
- [Source: `_bmad-output/implementation-artifacts/2-3-poranny-digest-przez-lokalny-harmonogram.md`]
- [Python sqlite3 transaction control](https://docs.python.org/3/library/sqlite3.html) — obecny adapter używa jawnego `BEGIN IMMEDIATE`; zachowaj atomowość operacji.
- [SQLite DELETE](https://www.sqlite.org/lang_delete.html) — kasowanie jest wykonywane transakcyjnie i w jawnej kolejności zależności aplikacyjnych.

## Dev Agent Record

### Completion Notes

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Dodano retencję wyników starszych niż 30 dni, automatycznie uruchamianą przed rzeczywistym Digestem oraz dostępną przez CLI.
- Dodano idempotentne usuwanie lokalnych danych konta z odzyskiwalną bramką SQLite; opcjonalne usunięcie tokenu korzysta z istniejącej ochrony przed symlinkami.
- Pełna regresja: `100 passed`; `uv run ruff check .` bez błędów.

### File List

- _bmad-output/implementation-artifacts/2-4-retencja-i-reczne-usuwanie-lokalnych-danych.md
- README.md
- src/gmail_mcp/domain/local_data.py
- src/gmail_mcp/application/local_data.py
- src/gmail_mcp/adapters/sqlite_analysis_state.py
- src/gmail_mcp/bootstrap/cli.py
- tests/unit/test_local_data.py
- tests/unit/test_sqlite_analysis_state.py
- tests/unit/test_gmail_connection.py

## Change Log

- 2026-07-29: Utworzono Story 2.4 z kontekstem retencji, trwałej blokady usuwania, SQLite i bezpiecznego tokenu OAuth.
- 2026-07-29: Zaimplementowano retencję i ręczne usuwanie lokalnych danych; status review.

### Review Findings

- [x] [Review][Patch] Nie pozwalaj `save_digest()` odtworzyć danych po rozpoczęciu usuwania konta [src/gmail_mcp/adapters/sqlite_analysis_state.py:102]
- [x] [Review][Patch] Porównuj timestampy retencji jako chwile UTC, nie jako tekst ISO z offsetem [src/gmail_mcp/adapters/sqlite_analysis_state.py:166]
- [x] [Review][Patch] Umożliw usunięcie lokalnych danych i brakującego tokenu bez sprawnego OAuth; CLI nie może wypisać tracebacku [src/gmail_mcp/bootstrap/cli.py:121]
- [x] [Review][Patch] Odnawiaj albo niezawodnie utrzymuj bramkę usuwania przez całe usuwanie, aby jej lease nie wygasł przed końcem [src/gmail_mcp/adapters/sqlite_analysis_state.py:583]
