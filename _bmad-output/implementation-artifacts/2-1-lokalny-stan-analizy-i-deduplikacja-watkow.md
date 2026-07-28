---
title: 'Story 2.1: Lokalny stan analizy i deduplikacja Wątków'
status: done
baseline_commit: 655db7d4f5e81a5c3f33c0e6421f359e369c34ef
created: 2026-07-28
---

# Story 2.1: Lokalny stan analizy i deduplikacja Wątków

## Story

As a właściciel narzędzia,
I want aby aplikacja rozpoznawała nowe lub zmienione Wątki i prowadziła trwały stan analizy,
so that nie płacę ponownie za tę samą analizę ani nie otrzymuję niespójnych wyników.

## Acceptance Criteria

1. Przy połączonym koncie i aktywnym filtrze kandydaci są wątkami, a kwalifikują się tylko po nowej wiadomości lub po rozpoczęciu spełniania filtra.
2. Rozpoczęcie analizy atomowo zapisuje `AnalysisRun` z migawką wejścia i statusem `running`, a kandydaci zostają przejęci przed wywołaniem AI.
3. Równoległe uruchomienie dla tego samego konta nie tworzy duplikatów; wynik uczciwie wskazuje `complete`, `partial` albo `failed`.
4. Niezmieniony, wcześniej podsumowany wątek nie jest ponownie kwalifikowany bez jawnego `reanalysis`; takie żądanie jest trwałe i odrębne.

## Tasks / Subtasks

- [x] Zdefiniować w `domain/analysis_state.py` niezmienne wartości: `ThreadCandidate`, `AnalysisRun`, statusy i hash migawki; bez importów SQLite/Gmail SDK. (AC 1–4)
- [x] Dodać w `application/analysis_state.py` Port repozytorium oraz use case atomowego planowania analizy z blokadą per konto. (AC 2–4)
- [x] Zaimplementować `adapters/sqlite_analysis_state.py` z transakcjami, schematem SQLite, unikalnością per konto/wątek oraz `BEGIN IMMEDIATE`. (AC 2–4)
- [x] Rozszerzyć `bootstrap/paths.py` tylko o wykorzystanie istniejącej ścieżki SQLite; nie dodawać CLI, MCP, cron ani wywołań AI. (AC 2)
- [x] Dodać unit tests fake repozytorium oraz testy kontraktowe SQLite dla deduplikacji, reanalysis, równoległego przejęcia i trwałości. (AC 1–4)

## Dev Notes

- Zachowaj Ports-and-Adapters: domena bez SDK, application definiuje Port, adapter SQLite implementuje Port, bootstrap składa zależności.
- Stan jest namespacowany fingerprintem konta z Story 1.3. SQLite przechowuje wyłącznie identyfikatory, hashe, metadane i stany; nigdy treść wątku ani załączniki.
- `AnalysisRun` musi zawierać niezmienną migawkę uporządkowanych kandydatów i hash wejścia. Nie implementuj jeszcze podsumowania AI, Digestu, harmonogramu ani MCP.
- Użyj standardowego `sqlite3`; nie dodawaj zależności. Błędy adaptera mapuj na bezpieczne wyniki aplikacji.
- Testy muszą wykonywać się bez Gmaila, kluczy AI i sieci. Użyj `tmp_path` dla SQLite oraz fake Portów dla application.

### References

- `_bmad-output/planning-artifacts/epics.md`, Story 2.1.
- `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md`, AD-1, AD-3, AD-4, AD-5, AD-7, AD-8, AD-10.
- `_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md`.

## Dev Agent Record

### Completion Notes

- Dodano planowanie kandydatów thread-first, deduplikację SQLite, atomową migawkę `AnalysisRun`, blokadę per konto i trwałą historię członkostwa filtra.
- Run zapisuje wymuszoną reanalizę oraz wynik per kandydat; po błędzie ponawiane są wyłącznie nieudane wątki.
- Zweryfikowano deduplikację, zmianę wiadomości, wejście/wyjście z filtra, reanalizę, trwałość kolejności migawki, równoległe przejęcie i stany terminalne; `66 passed`, Ruff czysty.

### File List

- src/gmail_mcp/domain/analysis_state.py
- src/gmail_mcp/application/analysis_state.py
- src/gmail_mcp/adapters/sqlite_analysis_state.py
- src/gmail_mcp/adapters/gmail_oauth.py
- tests/unit/test_analysis_state.py
- tests/unit/test_analysis_planning.py
- tests/unit/test_sqlite_analysis_state.py
- tests/unit/test_gmail_oauth.py

## Change Log

- 2026-07-28: Zaimplementowano Story 2.1 i poprawiono 10 ustaleń z code review.

### Review Findings

- [x] [Review][Patch] Po `failed` ponawiaj nieprzetworzone kandydaty, a po `partial` wyłącznie kandydaty bez sukcesu — wymaga trwałego wyniku per kandydat. [AC 3–4; AD-7, AD-10; src/gmail_mcp/adapters/sqlite_analysis_state.py:49]
- [x] [Review][Patch] Śledź historię członkostwa per filtr: kwalifikuj nową wiadomość albo przejście „poza filtrem → w filtrze”, a nie samą zmianę `filter_hash`. [AC 1; src/gmail_mcp/adapters/sqlite_analysis_state.py:54]
- [x] [Review][Patch] Zwracaj bezpieczny wynik aplikacyjny ze statusem `complete` / `partial` / `failed` i krótkim powodem; nie propaguj błędów SQLite do użytkownika. [AC 3; Dev Notes; src/gmail_mcp/application/analysis_state.py:30]
- [x] [Review][Patch] Trwała migawka nie zachowuje kolejności wejścia [src/gmail_mcp/adapters/sqlite_analysis_state.py:27]
- [x] [Review][Patch] Powtórzony `thread_id` w żądaniu reanalizy przerywa transakcję [src/gmail_mcp/adapters/sqlite_analysis_state.py:58]
- [x] [Review][Patch] Wymuszona reanaliza nie jest trwale oznaczana w `AnalysisRun` [src/gmail_mcp/adapters/sqlite_analysis_state.py:34]
- [x] [Review][Patch] Końcowy status runu może nadpisać wcześniejszy stan terminalny lub potwierdzić nieistniejący run [src/gmail_mcp/adapters/sqlite_analysis_state.py:101]
- [x] [Review][Patch] Port aplikacyjny nie obejmuje finalizacji runu, choć adapter mutuje stan bez use case [src/gmail_mcp/application/analysis_state.py:11]
- [x] [Review][Patch] Brak walidacji zgodności fingerprintu kandydata z kontem planu [src/gmail_mcp/adapters/sqlite_analysis_state.py:50]
- [x] [Review][Patch] Błąd pobrania metadanych jednego wątku przerywa całe wykrywanie kandydatów [src/gmail_mcp/adapters/gmail_oauth.py:144]

### Re-review Findings

- [x] [Review][Patch] Odzyskuj osierocone `running` runy po lease 15 minut: oznacz je `failed` i zwalniaj ich przejęcia przed kolejnym planowaniem. [AC 3; AD-10; src/gmail_mcp/adapters/sqlite_analysis_state.py:107]
- [x] [Review][Patch] Zapisuj UTC `created_at` runu oraz czas najnowszej wiadomości każdego kandydata; wyliczaj z migawki pokryty zakres czasu runu. [AD-7; src/gmail_mcp/domain/analysis_state.py:20]
- [x] [Review][Patch] Weryfikuj, że obiekt `AnalysisRun` przekazany do `finish()` odpowiada zapisanej migawce i kontu [src/gmail_mcp/adapters/sqlite_analysis_state.py:156]
- [x] [Review][Patch] Nie zwracaj pamięciowego `failed` po niepoprawnym `partial`, pozostawiając trwały run jako `running` [src/gmail_mcp/application/analysis_state.py:89]
- [x] [Review][Patch] Run bez kandydatów powinien zostać atomowo zapisany jako stan terminalny, nie bezterminowo `running` [src/gmail_mcp/adapters/sqlite_analysis_state.py:93]
- [x] [Review][Patch] Mapuj błąd powtórzonego tokenu stronicowania Gmaila na bezpieczny wynik [src/gmail_mcp/adapters/gmail_oauth.py:170]
- [x] [Review][Patch] Sprawdź, że Gmail zwraca to samo konto, którego fingerprint przekazano do planowania [src/gmail_mcp/adapters/gmail_oauth.py:131]
- [x] [Review][Patch] Wymagaj krótkiego powodu dla terminalnych stanów `partial` i `failed` [src/gmail_mcp/domain/analysis_state.py:42]
- [x] [Review][Patch] Nie pozwalaj ominąć historii członkostwa filtra przez opcjonalny `filter_hash` [src/gmail_mcp/application/analysis_state.py:51]
