---
title: 'Story 3.2: Potwierdzona analiza ad hoc przez wybranego dostawcę'
status: done
baseline_commit: 5a6ea11
created: 2026-07-29
---

# Story 3.2: Potwierdzona analiza ad hoc przez wybranego dostawcę

## Story

As a użytkownik klienta MCP,
I want zobaczyć dokładny zakres jednorazowej analizy i świadomie go potwierdzić,
so that używam OpenAI lub Claude do nowych pytań o Gmail bez przypadkowego ujawniania dodatkowych danych.

## Acceptance Criteria

1. Wywołanie `summarize_gmail` bez potwierdzenia tworzy wyłącznie podgląd metadanych: zwraca rozwiązany `GmailFilter.query`, uporządkowaną listę identyfikatorów Wątków wraz z ich liczbą oraz lokalnie wybranego Dostawcę AI. Gdy nie podano `query`, używany jest Aktywny Filtr Gmail aktywnego konta (albo istniejący filtr domyślny, jeśli nie zapisano aktywnego). Gdy podano `query`, jest to filtr wyłącznie jednorazowy: nie wolno wywołać `ActiveFilterRepositoryAdapter.save()` ani zmienić Aktywnego Filtru Gmail.
2. Potwierdzenie zaakceptowanego podglądu tworzy krótko żyjący, nieprzezroczysty i jednokrotnego użycia token potwierdzenia. Rekord potwierdzenia jest związany co najmniej z kontem, operacją `summarize_gmail`, hashem znormalizowanego filtra, **kolejnością** migawki Wątków, lokalnie wybranym dostawcą oraz hashem znormalizowanego oczyszczonego `AnalysisInput`. Nie zawiera ani nie ujawnia treści Wątków, promptu, sekretu ani klucza API.
3. Wykonanie bez prawidłowego tokenu — brakującego, wygasłego, już zużytego albo niedopasowanego do konta/operacji/filtra/migawki/dostawcy/wejścia — zwraca kanoniczny envelope `failed`, `data: null`, bezpieczny `reason` i `next_action` nakazujące odświeżenie podglądu. Przed tym zwrotem nie wolno pobrać pełnej treści Gmaila (`format=full`) ani wywołać AI.
4. Przy ważnym tokenie aplikacja analizuje wyłącznie zatwierdzoną, uporządkowaną migawkę Wątków, przez dokładnie lokalnie wybranego Dostawcę AI (`AI_PROVIDER`). Zwraca schema v1 `ThreadSummary` z faktycznie użytym dostawcą oraz prawdziwy status `complete`, `partial` albo `failed`; nie istnieje automatyczny fallback do drugiego dostawcy. Zmiana konta albo Wątku po podglądzie nie rozszerza zakresu — skutkuje uczciwym wynikiem częściowym/błędem tylko dla zatwierdzonej migawki.
5. FastMCP nadal wystawia dokładnie trzy narzędzia, lokalnie przez `stdio`, a wszystkie trzy odpowiedzi zachowują envelope `{"status", "data", "reason", "next_action"}`. `compare_summaries` pozostaje bezpiecznym placeholderem Story 3.3; `summarize_gmail` nie wykonuje zapisu, wysyłki ani usunięcia w Gmailu.

## Kontrakt przepływu MCP

`summarize_gmail` implementuje jeden jawny protokół trzech kroków; nazwy parametrów mogą zostać dobrane idiomatycznie dla FastMCP, ale semantyka musi pozostać poniższa.

1. **Podgląd** — klient przekazuje opcjonalny `query`. Use case rozwiązuje filtr oraz pobiera wyłącznie listę/metadata Wątków (`thread-first`), zapisuje krótko żyjące odwołanie do podglądu i zwraca: `phase: "preview"`, filtr, uporządkowane `thread_ids`, `thread_count`, `provider` i token/identyfikator potrzebny do potwierdzenia. Nie pobiera body ani nie wywołuje AI.
2. **Potwierdzenie** — klient przekazuje odwołanie podglądu oraz jawną zgodę. Dopiero po tej zgodzie można efemerycznie pobrać i oczyścić treść dokładnie z migawki, utworzyć hash `AnalysisInput` i wystawić finalny token wykonania. Token jest opaque; w odpowiedzi nie ma body ani promptu. Błąd pobrania/zmiana Wątku nie może dodać Wątku do zakresu.
3. **Wykonanie** — klient przekazuje finalny token. Use case atomowo sprawdza i konsumuje token przed jakimkolwiek odczytem pełnej treści lub wywołaniem dostawcy. Ponownie pobrane i oczyszczone dane muszą odpowiadać hashowi potwierdzonego wejścia; różnica oznacza `failed`/`partial`, nigdy podmianę danych. Token nie może zostać użyty ponownie, także przy równoległych wywołaniach.

Jeśli implementacja połączy kroki 1–2 w inny kształt parametrów narzędzia, musi zachować tę samą granicę: pełna treść jest czytana dopiero po jawnej akceptacji podglądu, a **przed wykonaniem** istnieje token związany z hashem oczyszczonego wejścia. Surowej treści nie wolno przyjmować jako argumentu MCP.

## Tasks / Subtasks

- [x] Zdefiniuj wartości domenowe i Porty potwierdzenia. (AC: 1–4)
  - [x] Dodaj nieprzezroczysty model preview/confirmation z walidacją TTL, jednorazowości, konta, operacji, filtra, uporządkowanej migawki, dostawcy i hashów; zegar/generator tokenów wstrzykuj przez Port lub funkcję testową.
  - [x] Hashuj wartość po tej samej normalizacji, którą faktycznie wykonuje kod (`GmailFilter.query`, kolejność kandydatów i oczyszczony tekst); nie sortuj Wątków i nie używaj `AnalysisRun.input_hash` jako substytutu hasha treści.
  - [x] W local state przechowuj co najwyżej hashe, identyfikatory, status zużycia i termin ważności; token zwracany klientowi musi być losowy, opaque i nie może być logowany.
- [x] Dodaj application use case dla podglądu, potwierdzenia i wykonania analizy ad hoc. (AC: 1–4)
  - [x] Reużyj `GmailOAuthAdapter.find_thread_candidates()` dla podglądu (metadata) oraz `fetch_clean_text()` dla efemerycznego body po zgodzie; zachowaj jego kontrolę fingerprintu i `latest_message_id`.
  - [x] Rozwiąż aktywny filtr przez istniejący port/repozytorium; dla filtra jednorazowego twórz tylko `GmailFilter(query)`, bez persystencji.
  - [x] Przed wykonaniem atomowo zużyj ważne potwierdzenie; błędny token kończy się przed `fetch_clean_text()` i `SummaryProviderPort.summarize()`.
  - [x] Użyj istniejącego `PlanAnalysis`/`FinishAnalysis`, `AnalysisRun` i `SummarizeAnalysisRun` albo rozszerz je minimalnie, zachowując blokadę per konto, immutable snapshot, SQLite single writer i statusy terminalne.
  - [x] Zbuduj dane odpowiedzi z `ThreadSummary` schema v1, ze źródłowym `thread_id`/linkiem, actions, priority, provider i disclaimerem; `partial`/`failed` wymagają reason oraz next action.
- [x] Zaimplementuj adapter lokalnego stanu potwierdzeń i bezpieczną integrację SQLite. (AC: 2–4)
  - [x] Preferuj nową tabelę/adapter (lub wyraźnie wydzielony port) z transakcyjnym „validate-and-consume”; tokeny z różnych kont nie mogą się mieszać.
  - [x] Nie przechowuj oczyszczonych ani surowych body; wprowadź bezpieczne czyszczenie wygasłych rekordów. Błędy SQLite przetłumacz na bezpieczny błąd aplikacyjny.
  - [x] Nie obchodź bramki usuwania danych, claims ani reguł deduplikacji z `SqliteAnalysisStateAdapter`.
- [x] Zastąp placeholder `summarize_gmail` w FastMCP i złóż zależności w bootstrapie. (AC: 1–5)
  - [x] Rozszerz `create_server()` bez dodawania czwartego toola i zachowaj `get_daily_digest`/`compare_summaries` bez regresji.
  - [x] Ładuj `load_settings()` tylko w `bootstrap/mcp.py`; użyj `create_summary_provider(settings)`, który instancjuje dokładnie `settings.ai_provider` i nie ma fallbacku. Błąd konfiguracji zwracaj bez nazwy sekretu ani jego wartości.
  - [x] Zachowaj stdio-only (stdout wyłącznie MCP, diagnostyka na stderr); nie wprowadzaj HTTP/SSE ani importów SDK do `domain/`/`application/`.
- [x] Dodaj testy od domeny do adaptera FastMCP. (AC: 1–5)
  - [x] Fakes dla portów: aktywny filtr vs one-off, deterministyczny zegar/token, kolejność Wątków oraz wybrany dostawca.
  - [x] Udowodnij, że preview nie czyta body i nie wzywa AI; one-off nie zmienia pliku/repozytorium aktywnego filtra.
  - [x] Udowodnij, że brakły/wygasły/użyty/niedopasowany token wywołuje zero `fetch_clean_text` i zero `summarize`; przetestuj mismatch konta, operation, filtra, provider, kolejności/snapshotu i hasha wejścia.
  - [x] Udowodnij atomową jednokrotność przy dwóch wykonaniach, brak fallbacku oraz poprawną agregację complete/partial/failed.
  - [x] Przetestuj zmianę konta oraz zmianę/zanik Wątku między podglądem a wykonaniem; nie może dojść do scope expansion.
  - [x] Uruchom `uv run pytest -q` oraz `uv run ruff check .`; testy nie używają sieci, OAuth, prawdziwych kluczy ani treści poczty.

### Review Findings

- [x] [Review][Patch] Nie zgłaszaj `complete`, gdy aktywne claimy odebrały część zatwierdzonej migawki; wymagaj, aby `run.candidates` dokładnie odpowiadało tokenowi albo zwróć bezpieczny `partial`/`failed`. [src/gmail_mcp/application/confirmed_analysis.py:205]
- [x] [Review][Patch] Zapisuj i weryfikuj niezależny hash uporządkowanej migawki w SQLite przed deserializacją/wykonaniem, aby uszkodzony rekord nie mógł podmienić Wątków poza zatwierdzonym zakresem. [src/gmail_mcp/adapters/sqlite_confirmation.py:22]
- [x] [Review][Patch] Włącz `analysis_confirmation` do bramki i ręcznego usuwania danych konta; w przeciwnym razie nieusunięty token może po czyszczeniu ponownie odczytać Gmail i wywołać AI. [src/gmail_mcp/adapters/sqlite_analysis_state.py:258]
- [x] [Review][Patch] Traktuj jawnie podany pusty `confirmation_token` jako nieprawidłowe wykonanie, nie jako nowy preview. [src/gmail_mcp/adapters/fastmcp_server.py:47]

## Dev Notes

### Obowiązujące granice architektoniczne

- Zachowaj Hexagonal / Ports-and-Adapters: domena nie importuje SDK, application zależy tylko od domain i portów, a `bootstrap/` jest jedynym composition rootem. [Source: `ARCHITECTURE-SPINE.md#AD-1`]
- FastMCP pozostaje wyłącznie lokalnym adapterem `stdio` i deleguje do use case’ów. Nie dodawaj REST, HTTP/SSE ani funkcji zapisu Gmaila. [Source: `ARCHITECTURE-SPINE.md#AD-2`]
- Jedna usługa application jest właścicielem mutacji SQLite. Wykorzystaj istniejącą blokadę `PlanAnalysis._locks[account]` i transakcję SQLite dla claims/zużycia tokenu. [Source: `ARCHITECTURE-SPINE.md#AD-3`, `#AD-10`]
- Gmail jest wyłącznie `gmail.readonly`, kandydaci są thread-first. Filtr one-off służy tylko do `summarize_gmail`, a aktywny filtr nadal ogranicza scheduler oraz przyszłe `compare_summaries`. [Source: `ARCHITECTURE-SPINE.md#AD-5`]
- Dostawca jest tylko jednym z `openai`/`claude`, wskazanym lokalnie w `Settings.ai_provider`; `create_summary_provider()` już eliminuje fallback. Nie twórz dostawcy z argumentu MCP. [Source: `ARCHITECTURE-SPINE.md#AD-6`]
- Pełne body i załączniki pozostają poza SQLite, logami, tokenem i odpowiedzią MCP. `sanitize_thread_text()` jest istniejącą normalizacją podpisów i cytatów; jej wynik jest jedynym wejściem do hashowania oraz AI. [Source: `ARCHITECTURE-SPINE.md#AD-4`, `#AD-8`, `src/gmail_mcp/application/thread_content.py`]
- Odpowiedzi są prawdziwe: `complete` ma `reason`/`next_action` równe `null`; `partial`/`failed` mają niepuste bezpieczne pola. [Source: `ARCHITECTURE-SPINE.md#AD-7`, `3-1-lokalny-serwer-fastmcp-i-odczyt-digestu.md#Acceptance Criteria`]

### Istniejące elementy do rozszerzenia, nie duplikowania

- `domain/analysis_state.py`: `AnalysisRun` ma immutable migawkę metadanych i hash metadanych. To **nie** jest hash oczyszczonego `AnalysisInput` wymagany dla potwierdzenia.
- `application/analysis_state.py`: `PlanActiveFilterAnalysis` pokazuje wzorzec fingerprint → filtr → `find_thread_candidates()` → `PlanAnalysis`; Story 3.2 potrzebuje analogicznego wariantu dla query jednorazowego, bez `save()` filtra.
- `adapters/gmail_oauth.py`: `find_thread_candidates()` pobiera metadata, a `fetch_clean_text()` weryfikuje konto oraz `latest_message_id`, pomija załączniki i sanitizuje tekst. Nie zastępuj tej kontroli nowym odczytem Gmaila.
- `application/thread_summary.py`: `SummarizeAnalysisRun` waliduje schema v1, konto, thread, provider i zapisuje hash tekstu; rozszerz fasadę wokół niego zamiast duplikować walidację podsumowania.
- `adapters/sqlite_analysis_state.py`: `plan()` zapisuje uporządkowane kandydaty i claims, `run_snapshot()` odczytuje kolejność. Reużyj go dla trwałej migawki, zachowując istniejące reguły deduplikacji/retencji/usuwania.
- `adapters/fastmcp_server.py`: obecny placeholder ma być zastąpiony; jego `_failed()` oraz kontrakt envelope są wzorcem kompatybilności z klientem.

### Project Structure Notes

- Przewidywane nowe moduły: `src/gmail_mcp/domain/confirmation.py`, `src/gmail_mcp/application/confirmed_analysis.py` oraz adapter persystencji potwierdzeń (wydzielony albo rozszerzający SQLite).
- Przewidywane aktualizacje: `application/analysis_state.py`, `application/thread_summary.py`, `adapters/sqlite_analysis_state.py`, `adapters/fastmcp_server.py`, `bootstrap/mcp.py` oraz odpowiednie testy unit/adapter.
- Nie dodawaj nowej biblioteki do generowania tokenów; użyj standardowej biblioteki Pythona. Stosuj istniejący Python 3.12, `mcp>=1.27,<2` (lock: 1.28.1), FastMCP i konwencje Ruff. [Source: `pyproject.toml`, `ARCHITECTURE-SPINE.md#AD-11`]

### Wnioski z Story 3.1

- Serwer ma dokładnie trzy narzędzia, a placeholdery muszą być bezpieczne i pozbawione side effectów.
- Kontrakt `next_action` jest częścią envelope, nie opcjonalnym dodatkiem.
- Przed odczytem danych przypisanych do konta należy ponownie zweryfikować fingerprint aktywnego konta; identyczną ochronę zastosuj przy potwierdzeniu i wykonaniu.
- Uszkodzony lokalny stan nie może wyjść jako traceback ani spowodować sfabrykowanego wyniku.

### Git Intelligence

- `5a6ea11` zmergował Story 3.1: FastMCP, `GetDailyDigest`, bootstrap stdio i hydrację Digestu.
- `9c8a5a8` ustanowił testowy styl: małe fake Porty i testy FastMCP bez sieci; zachowaj go dla potwierdzeń.

## References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 3.2`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#FR-7`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#FR-9`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]
- [Source: `_bmad-output/implementation-artifacts/3-1-lokalny-serwer-fastmcp-i-odczyt-digestu.md`]

## Dev Agent Record

### Completion Notes

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Zaimplementowano trzyfazowe `summarize_gmail`: preview metadanych, jawne potwierdzenie i jednokrotne wykonanie tokenem związanym z kontem, filtrem, kolejnością Wątków, dostawcą oraz hashem oczyszczonego wejścia.
- Tokeny są losowe i opaque; SQLite zapisuje tylko hashe, metadata migawki, termin ważności oraz stan zużycia. Nie zapisuje body, promptu ani sekretów.
- Brakły, wygasły i powtórnie użyty token kończą się przed pobraniem pełnej treści oraz przed AI. Wykonanie używa dokładnie tekstu zweryfikowanego wobec hasha potwierdzenia.
- Walidacja: `uv run pytest -q` — 113 passed; `uv run ruff check .` — passed.
- Review: usunięto ryzyko utraty claimed Wątku, zabezpieczono hash migawki i usuwanie tokenów przy czyszczeniu konta oraz odrzucono pusty token wykonania. Końcowa walidacja: 116 passed, Ruff passed.

### File List

- _bmad-output/implementation-artifacts/3-2-potwierdzona-analiza-ad-hoc-przez-wybranego-dostawce.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/gmail_mcp/domain/confirmation.py
- src/gmail_mcp/application/confirmed_analysis.py
- src/gmail_mcp/application/thread_summary.py
- src/gmail_mcp/adapters/sqlite_confirmation.py
- src/gmail_mcp/adapters/sqlite_analysis_state.py
- src/gmail_mcp/adapters/fastmcp_server.py
- src/gmail_mcp/bootstrap/mcp.py
- tests/unit/test_confirmed_analysis.py
- tests/unit/test_sqlite_confirmation.py
- tests/unit/test_fastmcp_server.py

## Change Log

- 2026-07-29: Utworzono Story 3.2 z trzyfazowym, potwierdzonym przepływem analizy ad hoc oraz nieprzekraczalną granicą danych Gmaila.
- 2026-07-29: Zaimplementowano potwierdzoną analizę ad hoc przez lokalnie wybranego dostawcę; status review.
- 2026-07-29: Code review — zastosowano 4 poprawki; status done.
