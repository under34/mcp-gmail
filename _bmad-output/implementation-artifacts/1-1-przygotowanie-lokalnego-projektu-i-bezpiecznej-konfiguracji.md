---
baseline_commit: NO_VCS
---

# Story 1.1: Przygotowanie lokalnego projektu i bezpiecznej konfiguracji

Status: done

## Story

As a właściciel lokalnego narzędzia,
I want uruchomić projekt z walidowaną konfiguracją i prywatnym katalogiem danych,
so that mogę bezpiecznie dodać poświadczenia Gmaila oraz klucze AI bez ryzyka zapisania ich w repozytorium.

## Kontekst i granice

To pierwsza historia Epicu 1, odblokowująca OAuth (1.2) oraz konfigurację filtru i dostawców (1.3). Repozytorium nie ma kodu aplikacji ani poprzednich historii.

Zakres obejmuje wyłącznie szkielet Pythona, ustawienia, ścieżki danych, higienę Git i testy. Nie implementuj OAuth, Gmail API, SQLite, FastMCP/HTTP, crona ani adapterów OpenAI/Claude. Nie dodawaj Flaska ani publicznego endpointu.

## Acceptance Criteria

1. **Zatwierdzony build i układ warstw**
   - **Given** świeży checkout projektu
   - **When** uruchamiam `uv sync --locked`
   - **Then** projekt korzysta z Pythona 3.12 oraz zatwierdzonego `uv.lock`
   - **And** struktura źródeł zawiera `domain`, `application`, `adapters` i `bootstrap`.

2. **Konfiguracja bez ujawniania sekretów**
   - **Given** lokalna konfiguracja
   - **When** aplikacja ładuje ustawienia
   - **Then** klucze OpenAI i Claude są odczytywane wyłącznie ze środowiska procesu lub lokalnego `.env`
   - **And** brak klucza wymaganego dla wybranego dostawcy zwraca czytelny błąd konfiguracji bez ujawnienia wartości sekretu.

3. **Lokalne dane poza repozytorium**
   - **Given** uruchomienie aplikacji
   - **When** tworzony jest katalog danych użytkownika
   - **Then** katalog przechowuje przyszły token OAuth, SQLite i Digesty poza repozytorium
   - **And** `.env`, `credentials.json`, tokeny oraz dane aplikacji są ignorowane przez Git, a logi nie zawierają sekretów ani treści maili.

## Tasks / Subtasks

- [x] Utworzyć powtarzalny szkielet Pythona (AC: 1)
  - [x] Dodać `.python-version` z dokładnym `3.12`, `pyproject.toml` z `requires-python = ">=3.12,<3.13"`, układem `src/` i komendami test/lint.
  - [x] Zadeklarować ograniczenia runtime: `mcp>=1.27,<2`, `google-api-python-client==2.198.0`, `google-auth-oauthlib==1.4.0`, `openai==2.38.0`, `anthropic==0.117.0` oraz minimalne zależności konfiguracji/testowe.
  - [x] Wygenerować i zatwierdzić `uv.lock`; `uv sync --locked` musi działać od świeżego checkoutu.
  - [x] Utworzyć importowalne pakiety `src/gmail_mcp/{domain,application,adapters,bootstrap}/` i katalogi `tests/{unit,integration}/`.

- [x] Zaimplementować ustawienia wyłącznie w composition root (AC: 2)
  - [x] Dodać typowany `Settings` i `ConfigurationError` w `src/gmail_mcp/bootstrap/`; tylko `bootstrap/` czyta env lub ładuje `.env`.
  - [x] Udokumentować zmienne: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AI_PROVIDER` (`openai` jako domyślne lub `claude`) i opcjonalną ścieżkę do lokalnego `credentials.json` dla historii 1.2.
  - [x] Procesowe env ma pierwszeństwo nad `.env`; ustawienia są ładowane raz i przekazywane jako zależność, nigdy logowane lub serializowane.
  - [x] Walidować dostawcę i wymagać wyłącznie klucza wybranego dostawcy. Nie wymagaj obu kluczy i nie dodawaj fallbacku.
  - [x] `ConfigurationError` wskazuje nazwę brakującej zmiennej i kolejne działanie, nigdy jej wartość ani cały obiekt ustawień.

- [x] Utworzyć bezpieczne ścieżki aplikacji i ochronę Git (AC: 3)
  - [x] W `bootstrap/paths.py` wyznaczyć katalog per-user przez `platformdirs.user_data_dir("gmail-mcp")`, nigdy przez `./data` lub `token.json` w checkoutcie.
  - [x] Udostępnić ścieżki dla przyszłego tokenu OAuth, SQLite i Digestów; tworzyć katalog przy pierwszym użyciu. Na POSIX stosować `0700` dla katalogu i `0600` dla plików sekretów, jeśli wspierane.
  - [x] Dodać `.gitignore` dla `.env`, `.env.*` z wyjątkiem `.env.example`, `credentials.json`, tokenów, baz/danych, `.venv`, cache, coverage i `__pycache__`. Nie ignorować `uv.lock`, kodu ani zanonimizowanych fixture'ów.
  - [x] Dodać `.env.example` bez wartości sekretów oraz README: `uv sync --locked`, lokalna konfiguracja, miejsce `credentials.json` i lokalizacja app-data.
  - [x] Skonfigurować logowanie bez dumpowania ustawień, sekretów, treści/załączników Gmaila lub surowych wyjątków zawierających wejście.

- [x] Pokryć fundament testami bez sieci (AC: 1, 2, 3)
  - [x] Testować importowalność pakietów i brak wywołań OAuth/SDK przy imporcie bootstrapu.
  - [x] Testować env i `.env`, pierwszeństwo env oraz bezpieczny `ConfigurationError` przy braku klucza wybranego dostawcy.
  - [x] Testować domyślny katalog danych poza repo oraz jego utworzenie, z testowym override ścieżki.
  - [x] Testować wzorce `.gitignore` dla `.env`, `credentials.json`, tokenu i lokalnych danych bez realnych sekretów.
  - [x] Uruchomić `uv sync --locked`, testy i lint. Testy nie mogą łączyć się z Gmail, OpenAI ani Claude.

### Review Findings

- [x] [Review][Patch] Traceback omija redakcję sekretów [src/gmail_mcp/bootstrap/logging.py:17] — naprawiono: filtr redaguje także sformatowane `exc_info` i `stack_info`; test regresji potwierdza brak sekretu w tracebacku.
- [x] [Review][Patch] Override katalogu danych może zapisać dane w checkoutcie [src/gmail_mcp/bootstrap/settings.py:55] — naprawiono: ścieżka danych jest rozwiązywana i odrzucana, gdy znajduje się w bieżącym checkoutcie; test obejmuje `GMAIL_MCP_DATA_DIR=.`.
- [x] [Review][Patch] Publiczna konfiguracja loggera nadal może wypisać sekret [src/gmail_mcp/bootstrap/logging.py:33] — naprawiono: logger usuwa pełne szczegóły `exc_info`/`exc_text`/`stack_info` niezależnie od przekazanej listy sekretów; smoke test publicznego `configure_logging()` nie wykazuje przecieku.
- [x] [Review][Patch] Walidacja katalogu danych nie wykrywa dowolnego checkoutu Git [src/gmail_mcp/bootstrap/paths.py:53] — naprawiono: ścieżka danych jest odrzucana, gdy jej przodek jest checkoutem Git tego projektu; test uruchamia proces z katalogu zewnętrznego.
- [x] [Review][Patch] Symlinki w katalogu danych mogą przekierować token lub zmienić obcy plik [src/gmail_mcp/bootstrap/paths.py:26] — naprawiono: symlinki katalogów danych i pliku tokenu są odrzucane przed `mkdir` lub `chmod`.

## Dev Notes

### Krytyczne ograniczenia architektury

- Hexagonal / Ports-and-Adapters: `domain/` nie importuje SDK; `application/` zależy wyłącznie od domain i Portów; adaptery je zaimplementują później; `bootstrap/` to jedyny composition root.
- Moduły poza `bootstrap/` nie odczytują env. Ustawienia są ładowane raz w bootstrapie.
- MVP jest lokalne i jednoużytkownikowe. Docelowy MCP to FastMCP przez `stdio`; nie twórz REST/Flask ani zdalnego hostingu.
- OpenAI jest domyślny; użytkownik lokalnie wybiera OpenAI lub Claude dla Digestu i `summarize_gmail`. Brak klucza wybranego dostawcy to błąd konfiguracji, bez automatycznej zmiany modelu.
- Pełne treści Wątków i załączniki nie mogą trafić do Git, trwałych danych ani logów. W tej historii nie przetwarzaj ich.
- Nie propaguj nieaktualnego ograniczenia z `C4-PORTFOLIO.md` (Claude tylko dla porównania); obowiązującym źródłem są PRD i Architecture Spine.

### Biblioteki i aktualne informacje techniczne

- `uv sync --locked` ma przerwać pracę przy nieaktualnym lockfile — jest to wymagane zabezpieczenie powtarzalnego builda. [Source: Astral uv — https://docs.astral.sh/uv/concepts/projects/sync/]
- `platformdirs.user_data_dir` jest wieloplatformowym miejscem dla trwałych danych aplikacji, w tym SQLite i stanu. [Source: platformdirs — https://platformdirs.readthedocs.io/en/stable/explanation.html]
- SDK OpenAI odczytuje `OPENAI_API_KEY` ze środowiska; klucza nie wolno wpisywać w kodzie ani śledzonej konfiguracji. [Source: OpenAI — https://platform.openai.com/docs/quickstart/make-your-first-api-request]

### Granice i zależności dla następnych historii

- Story 1.2 użyje ścieżki `credentials.json`, katalogu tokenu i bootstrapu błędów; OAuth i scope Gmail należą wyłącznie do 1.2.
- Story 1.3 użyje `AI_PROVIDER` i kluczy obu dostawców; walidacja filtru Gmail oraz zapis Aktywnego Filtru należą do 1.3.
- SQLite, retencja, blokady i `AnalysisRun` należą do Epicu 2; tutaj przygotuj wyłącznie bezpieczną ścieżkę.

### Project Structure Notes

```text
src/gmail_mcp/
  domain/
  application/
  adapters/
  bootstrap/        # Settings, paths, logging, composition root
tests/
  unit/
  integration/
docs/
  architecture/
```

Nie istnieją pliki UPDATE ani poprzednie commity implementacyjne — wszystkie pliki tej historii są nowe. Utrzymaj `src/` jako jedyny pakiet aplikacji.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1: Przygotowanie lokalnego projektu i bezpiecznej konfiguracji]
- [Source: _bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#4.1 Bezpieczne połączenie i konfiguracja lokalna]
- [Source: _bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#4.4 Wybór Dostawcy AI i kontrola danych]
- [Source: _bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md#5. Przekrojowe wymagania jakościowe]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-1 — Dependency direction]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-4 — Data and secret boundary]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md#AD-11 — Reproducible build seed]

## Dev Agent Record

### Agent Model Used

GPT-5.6 Codex

### Debug Log References

- RED: `uv run --locked pytest tests/unit/test_bootstrap.py -q` — potwierdzono brak modułu bootstrap przed implementacją.
- GREEN/DoD: `uv sync --locked`, `uv run --locked pytest -q` (10 passed), `uv run --locked ruff check .` i smoke importu warstw zakończone powodzeniem.
- Walidacja bezpieczeństwa: `git check-ignore --no-index` potwierdził ignorowanie `.env`, `credentials.json`, tokenu, SQLite i `.venv`.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Zweryfikowano aktualne źródła dla `uv --locked`, lokalnych katalogów danych i konfiguracji klucza OpenAI.
- Brak poprzednich historii, kodu aplikacji i commitów implementacyjnych do odziedziczenia.
- Zaimplementowano instalowalny pakiet Python 3.12 z zatwierdzonym `uv.lock`, rozdzielonymi warstwami oraz testami bez połączeń sieciowych.
- Dodano konfigurację env/.env z wyborem OpenAI/Claude bez fallbacku, prywatne ścieżki app-data i redakcję znanych sekretów w logach.
- Code review: naprawiono redakcję sekretów w tracebackach i zablokowano katalog danych wewnątrz checkoutu; `pytest` (12 passed) i `ruff` przechodzą.
- Ponowny code review: usunięto trzy dalsze luki dotyczące publicznego loggera, checkoutów Git i symlinków; `pytest` (15 passed), `ruff` oraz `uv sync --locked` przechodzą.

### File List

- `.env.example`
- `.gitignore`
- `.python-version`
- `README.md`
- `docs/architecture/.gitkeep`
- `pyproject.toml`
- `src/gmail_mcp/__init__.py`
- `src/gmail_mcp/adapters/__init__.py`
- `src/gmail_mcp/application/__init__.py`
- `src/gmail_mcp/bootstrap/__init__.py`
- `src/gmail_mcp/bootstrap/logging.py`
- `src/gmail_mcp/bootstrap/paths.py`
- `src/gmail_mcp/bootstrap/settings.py`
- `src/gmail_mcp/domain/__init__.py`
- `tests/integration/.gitkeep`
- `tests/unit/test_bootstrap.py`
- `uv.lock`
- `_bmad-output/implementation-artifacts/1-1-przygotowanie-lokalnego-projektu-i-bezpiecznej-konfiguracji.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-07-27: Utworzono bezpieczny szkielet projektu, konfigurację lokalną, ścieżki danych i testy dla Story 1.1.
- 2026-07-27: Code review — naprawiono 2 findings wysokiego wpływu.
- 2026-07-27: Ponowny code review — naprawiono 3 findings bezpieczeństwa.
