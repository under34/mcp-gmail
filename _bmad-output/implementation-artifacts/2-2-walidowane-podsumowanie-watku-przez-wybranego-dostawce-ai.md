---
title: 'Story 2.2: Walidowane podsumowanie Wątku przez wybranego Dostawcę AI'
status: ready-for-dev
baseline_commit: a5b6b88b44c66c6ac348fbc113360833158394ef
created: 2026-07-28
---

# Story 2.2: Walidowane podsumowanie Wątku przez wybranego Dostawcę AI

## Story

As a właściciel narzędzia,
I want otrzymać krótkie i przewidywalne podsumowanie istotnego Wątku,
so that szybko rozpoznaję priorytet oraz działania bez ręcznego czytania całej korespondencji.

## Acceptance Criteria

1. Dla zakwalifikowanego Wątku wejście do wybranego Dostawcy AI usuwa załączniki, podpisy i zbędną cytowaną historię; pełna treść Wątku nie jest zapisywana ani logowana.
2. Poprawna odpowiedź jest walidowana jako `ThreadSummary` schema v1: streszczenie do trzech zdań, priorytet `wysoki`/`średni`/`niski`, działania (lub jawny brak), dostawca i status.
3. Błąd API albo niezgodny wynik kończy Wątek i `AnalysisRun` jako `partial` albo `failed` z bezpieczną przyczyną, bez automatycznego fallbacku.
4. Zapisane podsumowanie zawiera source `thread_id` albo link Gmaila oraz komunikat, że AI może być niepełne lub błędne.

## Tasks / Subtasks

- [ ] Dodaj `domain/thread_summary.py`: niezmienny `ThreadSummary` schema v1, ścisłą walidację priorytetu, maks. trzech zdań, jawnej listy działań, providera, statusu i źródła. (AC 2, 4)
- [ ] Dodaj `application/thread_summary.py` z `ThreadContentPort`, `SummaryProviderPort`, portem repozytorium i use case `SummarizeAnalysisRun`. Wejściem jest wyłącznie przejęta migawka `AnalysisRun.candidates`; po sukcesach wywołaj istniejący `FinishAnalysis`. (AC 1–3)
- [ ] Rozszerz `GmailOAuthAdapter` o kontrolowane pobranie jednego Wątku po claimie (`gmail.readonly`); nie pobieraj załączników i znormalizuj podpisy/cytaty przed providerem. (AC 1)
- [ ] Dodaj `OpenAISummaryProviderAdapter` i `ClaudeSummaryProviderAdapter` za tym samym portem. Użyj istniejącego wyboru providera z `Settings`, bez czytania env w adapterze i bez fallbacku. (AC 2–3)
- [ ] Dodaj minimalną trwałą tabelę summary (konto, thread/run ID, hash wejścia, schema version, zwalidowane pola, provider, status, reason, UTC timestamp), bez body/promptu/załączników. Zapis summary musi nastąpić przed oznaczeniem kandydata jako sukces. (AC 2–4)
- [ ] Testy domain/application/adapterów: sanitizacja, schema-invalid, błąd providera, `partial(successful_thread_ids)`, brak fallbacku, trwałość source/linku oraz brak raw body w SQLite/logach. (AC 1–4)

## Dev Notes

- Reużyj Story 2.1 — `PlanActiveFilterAnalysis` atomowo przejmuje kandydatów, `FinishAnalysis` kończy run. Nie twórz drugiej deduplikacji ani nie pobieraj treści przed claimem.
- Hexagonalność: domena bez Gmail/OpenAI/Anthropic/SQLite; Porty w `application`; SDK wyłącznie w adapterach; `bootstrap` jest jedynym composition rootem.
- Dla mieszanego wyniku przekaż dokładne `successful_thread_ids`; przy zerze sukcesów zwróć `failed` z krótkim reason. To zachowuje retry jedynie dla nieudanych Wątków.
- Nigdy nie zapisuj ani nie loguj body, załączników, promptu, surowej odpowiedzi czy sekretów. Link buduj z opaque thread ID, np. `https://mail.google.com/mail/u/0/#all/{thread_id}`.
- Nie dodawaj MCP, crona, Digestu, tokenu potwierdzenia ani jednorazowych filtrów — to Stories 2.3 i 3.x.

### Files and Tests

- Nowe: `domain/thread_summary.py`, `application/thread_summary.py`, adaptery OpenAI/Claude i testy fake-portów.
- Aktualizuj: `adapters/gmail_oauth.py`, `adapters/sqlite_analysis_state.py`, istniejące testy analysis/Gmail/SQLite.
- Weryfikacja: `uv run pytest -q` i `uv run ruff check .`, bez sieci, Gmaila i kluczy AI; `tmp_path`, monkeypatch i sanitizowane fixture’y.

### References

- `_bmad-output/planning-artifacts/epics.md`, Story 2.2 oraz FR-4.
- `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md`, AD-1, AD-3–AD-8, AD-10.
- `_bmad-output/implementation-artifacts/2-1-lokalny-stan-analizy-i-deduplikacja-watkow.md`.

## Dev Agent Record

### Completion Notes

- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List
