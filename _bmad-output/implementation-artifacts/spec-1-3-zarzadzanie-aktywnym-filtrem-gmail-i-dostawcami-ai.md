---
title: 'Story 1.3: Zarządzanie Aktywnym Filtrem Gmail i dostawcami AI'
type: 'feature'
created: '2026-07-28'
status: 'done'
baseline_commit: 'aafcc4c29c993b7008529e680e7f4115e716dc71'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Połączenie OAuth istnieje, ale użytkownik nie może jeszcze ograniczyć przyszłej analizy do kontrolowanego zakresu skrzynki ani sprawdzić, czy lokalnie wybrany dostawca AI jest gotowy do użycia.

**Approach:** Dodać trwały Aktywny Filtr Gmail, przechowywany osobno dla każdego połączonego konta, z bezpiecznym podglądem liczby pasujących wątków przed jawnym zapisem oraz raportowanie i walidację lokalnego wyboru OpenAI lub Claude z konfiguracji środowiskowej.

## Boundaries & Constraints

**Always:** Gmail pozostaje wyłącznie do odczytu i działa na wątkach; domyślny filtr to `in:inbox -category:promotions -category:social`. Użytkownik przekazuje niepuste zapytanie Gmail search (`--query`), w którym może użyć składni `from:`, `label:` i słów kluczowych; normalizacja query usuwa wyłącznie białe znaki na jego końcach i nie zmienia środka ani cytatów. Polecenie zapisu samo wykonuje podgląd tego samego query i wymaga flagi `--confirm`; nie może polegać na podglądzie z poprzedniego procesu. Każdy błąd listowania Gmaila, w tym błędny query, 401/403, timeout, 429/5xx albo powtarzający się token strony, daje `failed` i nie zapisuje filtra. Brak pliku dla konta oznacza aktywny filtr domyślny, jeszcze nieutrwalony; uszkodzony JSON albo nieobsługiwana wersja daje bezpieczny `failed` i nie jest nadpisywana przez odczyt/status. MVP obsługuje wiele lokalnych profili Gmail, z jednym aktywnym kontem naraz. Identyfikator profilu jest SHA-256 z `emailAddress.strip().lower()` zwróconego przez Gmail profile API; jego hex służy wyłącznie jako nazwa pliku, a zapisany JSON musi zawierać ten sam fingerprint i zostać odrzucony przy niezgodności. Klucze AI pochodzą tylko ze środowiska lub lokalnego `.env`, przy czym środowisko ma pierwszeństwo; `AI_PROVIDER` jest po `strip().lower()` wyłącznie `openai` lub `claude`, a pusta/inna wartość daje `failed`. Dostawca jest dostępny tylko z własnym kluczem niepustym po `strip()`, OpenAI jest wartością domyślną, bez automatycznego fallbacku. Konfiguracja filtra, tak jak token, jest lokalna, atomowa, prywatna i odporna na symlinki; nie zawiera wiadomości, identyfikatorów wątków ani sekretów.

**Ask First:** Dodatkowa składnia filtra wykraczająca poza bezpośrednie zapytanie Gmaila, zdalny interfejs MCP, SQLite, pobieranie treści wiadomości, wywołania OpenAI/Claude albo zmiana sposobu trwałego wyboru `AI_PROVIDER`.

**Never:** Nie modyfikować Gmaila, nie rozszerzać OAuth scope, nie logować treści maili/kluczy, nie zastępować aktywnego filtra po błędzie ani nie wybierać drugiego dostawcy przy braku lub błędzie pierwszego.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Podgląd i zapis | Połączone konto, `--query` albo wartość domyślna i `--confirm` | `preview-gmail-filter` pokazuje query i liczbę wątków; `set-gmail-filter --confirm` ponawia ten podgląd i atomowo zapisuje filtr konta | Wynik `complete`, bez listy maili ani wątków |
| Niewłaściwy filtr lub błąd listowania | Nieobsługiwane zapytanie, 401/403, timeout, 429/5xx albo zapętlona paginacja | Nie powstaje częściowy podgląd, a poprzedni aktywny filtr pozostaje zachowany | Wynik `failed`; dla autoryzacji instrukcja ponownego połączenia |
| Brak potwierdzenia lub stan lokalny | Brak `--confirm`, brak pliku, uszkodzony JSON albo nieznana wersja schematu | Brak potwierdzenia nic nie zapisuje; brak pliku raportuje domyślny filtr jako nieutrwalony; uszkodzony stan nie jest odczytywany ani nadpisywany przez status | Jasna instrukcja potwierdzenia albo bezpieczny `failed` |
| Dostawca AI | `AI_PROVIDER` wybiera OpenAI/Claude; klucz istnieje lub go brakuje | `ai-provider-status` pokazuje wybranego i dostępnych dostawców | Nieprawidłowa wartość lub brak klucza daje `failed`, bez sekretu i fallbacku |

</frozen-after-approval>

## Code Map

- `src/gmail_mcp/domain/` -- nowe niezmienne wartości filtra i wyników bez zależności SDK.
- `src/gmail_mcp/application/` -- porty oraz use case’y podglądu, potwierdzonego zapisu i odczytu aktywnego filtra dla konta.
- `src/gmail_mcp/adapters/gmail_oauth.py` -- wykorzystanie istniejącego tokenu do thread-first podglądu Gmail API.
- `src/gmail_mcp/adapters/` -- bezpieczny adapter lokalnego pliku konfiguracji filtra.
- `src/gmail_mcp/bootstrap/settings.py` i `paths.py` -- rozdzielone odkrywanie dostępnych dostawców oraz prywatna ścieżka konfiguracji.
- `src/gmail_mcp/bootstrap/cli.py` -- komendy filtra i statusu dostawcy jako jedyny composition root.
- `tests/unit/` -- testy domeny, use case’ów, ustawień, adapterów i CLI bez prawdziwego Gmaila.
- `README.md`, `.env.example` -- instrukcje konfiguracji i użycia nowych lokalnych poleceń.

## Tasks & Acceptance

**Execution:**
- [x] `src/gmail_mcp/domain/gmail_filter.py` -- utworzyć walidowany, niemutowalny filtr, domyślną wartość, podgląd i bezpieczny kontrakt wyników; normalizować query wyłącznie przez `strip()` i odrzucać wynik pusty.
- [x] `src/gmail_mcp/application/gmail_filter.py` -- zdefiniować Porty Gmail/repozytorium oraz przypadki użycia, które wymagają połączenia, podglądają wątki i zapisują wyłącznie udany podgląd z tego samego wywołania oraz po jawnym potwierdzeniu.
- [x] `src/gmail_mcp/adapters/gmail_oauth.py` -- dodać odczyt listy `threads` z paginacją i bez wywołań write API; wykrywać powtórzony token strony, a każdy błąd listowania mapować na bezpieczny wynik bez częściowej liczby.
- [x] `src/gmail_mcp/adapters/active_filter_repository.py` oraz `src/gmail_mcp/bootstrap/paths.py` -- użyć SHA-256 ze znormalizowanego `emailAddress` jako fingerprintu i nazwy pliku profilu; zapisywać wersję schematu, fingerprint i query w osobnym dla konta prywatnym, atomowo zastępowanym pliku JSON z ochroną przed symlinkami; odrzucać niezgodny fingerprint oraz rozróżniać brak stanu od uszkodzenia i nieznanej wersji.
- [x] `src/gmail_mcp/bootstrap/settings.py` -- wystawić bezpieczny status skonfigurowanych dostawców i walidację wybranego dostawcy bez wymagania klucza nieaktywnego dostawcy; zachować `env > .env`, normalizację `AI_PROVIDER` przez `strip().lower()` oraz uznawać klucz za dostępny dopiero po niepustym `strip()`.
- [x] `src/gmail_mcp/bootstrap/cli.py` -- dodać `preview-gmail-filter [--query QUERY]`, `set-gmail-filter [--query QUERY] --confirm`, `gmail-filter-status` i `ai-provider-status`; zachować kody `0` dla `complete`, `1` dla `failed` oraz czytelny kontrakt wyjścia.
- [x] `tests/unit/` -- pokryć macierz I/O, query whitespace-only, paginację i błędy każdej strony, powtórzony token, zachowanie starego filtra po błędzie, brak/uszkodzenie/wersję JSON, fingerprint i filtr per konto, symlinki oraz wybór dostawcy z kluczem whitespace-only bez fallbacku.
- [x] `README.md` i `.env.example` -- opisać domyślny filtr, jawne potwierdzenie, ścieżki danych i ustawienie `AI_PROVIDER`.

**Acceptance Criteria:**
- Given połączone konto, when użytkownik podgląda poprawny filtr przez `preview-gmail-filter`, then widzi dokładne query i liczbę wszystkich pasujących wątków przed zapisem.
- Given poprawny filtr, when użytkownik uruchamia `set-gmail-filter --confirm`, then to samo wywołanie ponownie go podgląda, a następnie zapisuje jako aktywny tylko dla bieżącego konta; bez `--confirm` nic nie zapisuje.
- Given nieobsługiwany filtr, utracona autoryzacja lub błąd lokalnego zapisu, when zapis nie może dojść do skutku, then rezultat jest `failed`, poprzedni filtr pozostaje niezmieniony, a Gmail nie jest modyfikowany.
- Given konfiguracja OpenAI lub Claude, when sprawdzany jest wybrany dostawca, then `AI_PROVIDER` jest normalizowany i walidowany, środowisko ma pierwszeństwo przed `.env`, dostępność zależy wyłącznie od jego klucza, OpenAI jest domyślne, a brak klucza nie powoduje wyboru drugiego dostawcy.

## Design Notes

Oddzielny plik JSON na konto jest minimalnym trwałym stanem dla Story 1.3; SQLite i stan analizy należą do Epiku 2. SHA-256 z adresu zwróconego przez Gmail profile API jest wyłącznie technicznym fingerprintem do nazw plików i walidacji ich własności. Podgląd Gmaila powinien używać dokładnie tego samego query po `strip()`, które może zostać zapisane, oraz zliczać wszystkie strony odpowiedzi `threads.list`, nie `resultSizeEstimate` ani wiadomości. Błąd dowolnej strony lub powtórzony token unieważnia podgląd.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: wszystkie testy jednostkowe przechodzą bez dostępu do Google i bez otwarcia przeglądarki.
- `uv run ruff check .` -- expected: brak naruszeń stylu i importów.

### Review Findings

- [x] [Review][Decision] Izolacja filtra przy zmianie konta Gmail — wybrano osobny filtr dla każdego lokalnie rozpoznanego konta Gmail.
- [x] [Review][Patch] Przechowywać i odczytywać filtr per konto Gmail [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:55]
- [x] [Review][Patch] Zdefiniować dozwolony input filtra i kontrakt CLI [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:21]
- [x] [Review][Patch] Powiązać zapis z podglądem oraz bezpiecznie kończyć błędną paginację [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:31]
- [x] [Review][Patch] Ustalić semantykę braku, uszkodzenia i niezgodnej wersji lokalnego filtra [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:55]
- [x] [Review][Patch] Doprecyzować walidację i priorytet źródeł `AI_PROVIDER` [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:34]
- [x] [Review][Patch] Rozszerzyć testy o granice trwałości, błędy stron i konfigurację [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:58]
- [x] [Review][Decision] Zakres kont Gmail — wybrano wiele lokalnych profili z jednym aktywnym kontem naraz; publiczna usługa wieloużytkownikowa i równoległe przetwarzanie pozostają poza MVP.
- [x] [Review][Patch] Zdefiniować stabilny i bezpieczny identyfikator konta dla repozytorium filtra [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:21]
- [x] [Review][Patch] Zdefiniować minimalną normalizację query i kluczy dostawców [_bmad-output/implementation-artifacts/spec-1-3-zarzadzanie-aktywnym-filtrem-gmail-i-dostawcami-ai.md:21]

## Dev Agent Record

### Completion Notes

- Zaimplementowano aktywny filtr Gmail per konto, podgląd thread-first, bezpieczny zapis JSON i status dostawcy AI.
- Dodano testy domeny, repozytorium, use case'ów, CLI oraz paginacji Gmaila; `46 passed`, `ruff check .` przechodzi.

### File List

- src/gmail_mcp/domain/gmail_filter.py
- src/gmail_mcp/application/gmail_filter.py
- src/gmail_mcp/adapters/active_filter_repository.py
- src/gmail_mcp/adapters/gmail_oauth.py
- src/gmail_mcp/bootstrap/paths.py
- src/gmail_mcp/bootstrap/settings.py
- src/gmail_mcp/bootstrap/cli.py
- tests/unit/test_gmail_filter.py
- tests/unit/test_gmail_filter_application.py
- tests/unit/test_gmail_oauth.py
- tests/unit/test_gmail_connection.py
- tests/unit/test_bootstrap.py
- README.md

## Change Log

- 2026-07-28: Zaimplementowano Story 1.3; historia gotowa do review.
- 2026-07-28: Code review zaakceptowany po poprawce walidacji klucza whitespace-only.
