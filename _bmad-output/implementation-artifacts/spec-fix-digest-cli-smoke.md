---
title: 'Diagnostyka i wiarygodny wynik wykonania Daily Digest z CLI'
type: 'bugfix'
created: '2026-07-30'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'b752a2931410e22786102a2e2af3265f52a86b4e'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Uruchomienie `gmail-mcp run-daily-digest` w rzeczywistym środowisku nie dało użytkownikowi czytelnego wyniku ani zapisanego Digestu, mimo działającego OAuth i aktywnego filtra. Obecne obsługiwanie błędów ukrywa przyczynę, przez co nie da się odróżnić błędu Gmaila, dostawcy AI i lokalnego stanu.

**Approach:** Zapewnić bezpieczną obserwowalność błędów wykonania bez ujawniania treści maili lub kluczy oraz zagwarantować, że CLI zwraca jednoznaczny status i zachowuje bezpieczny wynik Digestu, gdy jest to możliwe.

## Boundaries & Constraints

**Always:** Zachować wyłącznie lokalny transport i brak modyfikacji Gmaila. Nie logować treści wiadomości, promptów, odpowiedzi dostawcy ani kluczy API. Nie zmieniać kontraktu istniejących narzędzi MCP. Zachować bieżące, niezatwierdzone zmiany jako część naprawy, o ile przejdą testy.

**Ask First:** Każde przechowywanie dodatkowych danych diagnostycznych, zmiana dostawcy AI, aktywnego filtra, danych OAuth lub wykonanie niszczącej operacji na lokalnym stanie.

**Never:** Nie dodawać fallbacku między OpenAI i Claude, nie drukować wyjątków dostawcy, nie wysyłać kolejnej analizy prawdziwych maili wyłącznie na potrzeby testu oraz nie zmieniać danych w Gmailu.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Provider failure | Dostawca podsumowań odrzuca żądanie | CLI zwraca `failed` lub `partial`, a wynik Digestu jest lokalnie dostępny | Log zawiera tylko nazwę dostawcy, typ wyjątku i identyfikator wątku; nie zawiera sekretu ani treści |
| Local persistence failure | SQLite nie zapisuje Digestu | CLI zwraca niezerowy kod i bezpieczny komunikat | Bez nieobsłużonego wyjątku lub pozornego sukcesu |
| Successful/empty run | Gmail zwraca zero kandydatów | CLI zwraca `complete: threads=0` i zapisuje wynik | Kod wyjścia 0 |
| Subprocess invocation | Zainstalowany entry point `gmail-mcp` | stdout kończy się jednoznacznym statusem, stderr nie zawiera danych wrażliwych | Test regresji pokrywa procesową ścieżkę CLI |

</frozen-after-approval>

## Code Map

- `src/gmail_mcp/bootstrap/cli.py` -- kompozycja i komunikat końcowy Daily Digest.
- `src/gmail_mcp/application/digest.py` -- zapisywanie bezpiecznego wyniku Digestu.
- `src/gmail_mcp/application/thread_summary.py` -- izolacja błędów pojedynczych podsumowań.
- `src/gmail_mcp/bootstrap/logging.py` -- redakcja sekretów w diagnostyce.
- `tests/unit/test_gmail_connection.py` -- test CLI i kody wyjścia.
- `tests/unit/test_summarize_analysis_run.py` -- bezpieczna diagnostyka nieudanego dostawcy.

## Tasks & Acceptance

**Execution:**

- [x] `src/gmail_mcp/application/thread_summary.py` -- raportować wyłącznie bezpieczne metadane niepowodzenia dostawcy, a następnie kontynuować pozostałe wątki -- umożliwia diagnozę bez ujawniania danych.
- [x] `src/gmail_mcp/bootstrap/cli.py` i `src/gmail_mcp/bootstrap/mcp.py` -- skonfigurować redagowane logowanie na granicy kompozycji -- ten sam standard dla CLI i MCP.
- [x] `src/gmail_mcp/application/digest.py` oraz `src/gmail_mcp/bootstrap/cli.py` -- zweryfikować i, jeśli potrzeba, naprawić ścieżkę zapisu oraz kod wyjścia dla częściowego i nieudanego Digestu -- użytkownik zawsze otrzymuje prawdziwy status.
- [x] `tests/unit/test_gmail_connection.py` i `tests/unit/test_summarize_analysis_run.py` -- dodać regresje dla bezpiecznego komunikatu, zapisu wyniku i kodu wyjścia -- zapobiega powrotowi cichego błędu.

**Acceptance Criteria:**

- Given provider podsumowań rzuca wyjątek zawierający dane wrażliwe, when Daily Digest kończy się niepowodzeniem, then CLI zwraca bezpieczny status, a log nie zawiera danych wyjątku.
- Given niepowodzenie części lub całości podsumowań, when lokalny stan jest dostępny, then ostatni Digest jest zapisany jako `partial` albo `failed` z kolejnym działaniem.
- Given uruchomienie CLI przez entry point, when proces kończy pracę, then zwraca przewidywalny kod wyjścia i końcowy wiersz statusu.
- Given istniejące przepływy MCP, when uruchamiane są testy regresji, then nadal oferują wyłącznie dozwolone narzędzia i nie ujawniają sekretów.

## Spec Change Log

## Design Notes

Logowanie ma służyć tylko operatorowi lokalnemu. Zapisujemy typ błędu, oczekiwanego dostawcę i identyfikator wątku; nie zapisujemy tekstu komunikatu wyjątku, bo biblioteki dostawców mogą umieścić w nim fragment żądania lub odpowiedzi.

## Verification

**Commands:**

- `uv run pytest -q tests/unit/test_gmail_connection.py tests/unit/test_summarize_analysis_run.py` -- expected: wszystkie testy przechodzą.
- `uv run pytest -q` -- expected: pełny zestaw przechodzi.
- `uv run ruff check src tests` -- expected: brak naruszeń.
- `uv run gmail-mcp run-daily-digest --scheduled` -- expected: jednoznaczny status bez połączenia z AI, jeśli zadanie nie jest należne.

## Suggested Review Order

**Fail-fast dostawcy**

- Zatrzymuje serię kosztownych wywołań po błędzie ogólnym dla dostawcy.
  [`thread_summary.py:86`](../../src/gmail_mcp/application/thread_summary.py#L86)

- Mapuje błędy autoryzacji, limitu i salda Claude na bezpieczny sygnał aplikacyjny.
  [`claude_summary.py:24`](../../src/gmail_mcp/adapters/claude_summary.py#L24)

- Przechowuje failed Digest bez częściowych pozycji i z właściwą instrukcją.
  [`digest.py:55`](../../src/gmail_mcp/application/digest.py#L55)

**Konfiguracja i regresje**

- Przekazuje nazwę wybranego dostawcy do bezpiecznej diagnostyki CLI.
  [`cli.py:83`](../../src/gmail_mcp/bootstrap/cli.py#L83)

- Weryfikuje wyjście CLI i entry point procesu bez połączeń z usługami zewnętrznymi.
  [`test_gmail_connection.py:121`](../../tests/unit/test_gmail_connection.py#L121)
