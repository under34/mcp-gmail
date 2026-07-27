---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - '_bmad-output/planning-artifacts/prds/prd-under_34@o2.pl-2026-07-27/prd.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-under_34@o2.pl-2026-07-27/ARCHITECTURE-SPINE.md'
---

# Usługa MCP dla Gmaila - Epic Breakdown

## Overview

Ten dokument rozkłada wymagania PRD i Architecture Spine na implementowalne epiki oraz historie. Ekstrakcja wymagań jest gotowa; projekt epików zostanie dodany po potwierdzeniu użytkownika.

## Requirements Inventory

### Functional Requirements

- **FR-1:** Użytkownik łączy jedno Konto Gmail przez OAuth wyłącznie z zakresem `gmail.readonly`, widzi konto, może się odłączyć i otrzymuje jasny błąd ponownej autoryzacji.
- **FR-2:** Użytkownik definiuje, podgląda, zapisuje i zmienia Filtr Gmail; zapisany filtr staje się Aktywnym Filtrem Gmail, a nieobsługiwany filtr nie rozszerza zakresu analizy.
- **FR-3:** Digest obejmuje tylko nowe Wątki lub Wątki, które zaczęły spełniać Aktywny Filtr Gmail, deduplikuje niezmienione Wątki i zawiera zakres, liczbę Wątków oraz link/uzasadnienie pozycji.
- **FR-4:** System zwraca Podsumowanie Wątku z maksymalnie trzema zdaniami, priorytetem `wysoki`/`średni`/`niski`, konkretnymi działaniami lub jawnym ich brakiem oraz linkiem do źródła.
- **FR-5:** Użytkownik konfiguruje lokalny Harmonogram o domyślnej godzinie 08:00; używa on lokalnie wybranego Dostawcy AI (OpenAI domyślnie), nie blokuje narzędzi MCP i uczciwie ujawnia nieudane wykonanie.
- **FR-6:** `get_daily_digest` zwraca ostatni Digest albo stan `failed` z instrukcją dalszego działania.
- **FR-7:** `summarize_gmail` przez lokalnie wybranego Dostawcę AI analizuje Aktywny lub jednorazowy Filtr Gmail po pokazaniu zakresu i potwierdzeniu; nie zmienia Aktywnego Filtru i nie modyfikuje Gmaila.
- **FR-8:** `compare_summaries` porównuje OpenAI i Claude wyłącznie dla Wątku z Aktywnego Filtru Gmail oraz po potwierdzeniu; zwraca osobne statusy dostawców i nie stosuje fallbacku.
- **FR-9:** Użytkownik lokalnie konfiguruje klucze dostawców; OpenAI jest domyślny, a OpenAI lub Claude może obsługiwać Digest i `summarize_gmail`; `compare_summaries` używa obu modeli.
- **FR-10:** System przechowuje lokalnie tylko identyfikatory, hashe, metadane i podsumowania, usuwa wyniki po 30 dniach oraz pozwala ręcznie usunąć stan i token OAuth.

### NonFunctional Requirements

- **NFR-1:** Treść Wątku służy wyłącznie do utworzenia żądanego Digestu lub Podsumowania Wątku.
- **NFR-2:** Każde narzędzie MCP zwraca `complete`, `partial` albo `failed` wraz z czytelną przyczyną i kolejnym działaniem.
- **NFR-3:** System nie rozszerza Aktywnego Filtru Gmail, nie modyfikuje Gmaila i nie zmienia Dostawcy AI bez lokalnej, jawnej konfiguracji użytkownika; `compare_summaries` wymaga osobnego potwierdzenia wysłania treści do obu dostawców.
- **NFR-4:** Wywołania Gmail API i AI dotyczą tylko nowych lub zmienionych Wątków, chyba że użytkownik jawnie zażąda ponownej analizy.
- **NFR-5:** Tokeny OAuth, klucze AI i wyniki są przechowywane lokalnie na komputerze użytkownika.

### Additional Requirements

- Python 3.12, `uv` i zatwierdzony `uv.lock`; MCP Python SDK pozostaje w stabilnej linii v1 (`>=1.27,<2`).
- Hexagonal / Ports-and-Adapters: `domain` nie importuje SDK; tylko `bootstrap` składa zależności; adaptery implementują Porty.
- FastMCP wystawia wyłącznie trzy narzędzia przez lokalne `stdio`; cron wywołuje CLI, nie niezależną logikę.
- Jedna usługa aplikacyjna posiada wyłączność na zapis do SQLite; blokada per konto i atomowy `AnalysisRun` chronią przed duplikacją i wyścigami.
- GmailAdapter działa thread-first i z `gmail.readonly`; Aktywny Filtr ogranicza harmonogram oraz porównanie modeli.
- `ThreadSummary` schema v1 ma jednolity format dla OpenAI i Claude; odpowiedzi są walidowane, a błędy jednego dostawcy pozostają jawne.
- Potwierdzenie analizy używa krótkotrwałego tokenu związanego z operacją, migawką filtra, kolejnością Wątków, dostawcą i hashem oczyszczonego wejścia.
- Sekrety są wyłącznie w środowisku lub lokalnym `.env`; OAuth token, SQLite i Digesty są w katalogu danych bieżącego użytkownika; logi nie zawierają treści maili ani sekretów.
- Usuwanie danych i odłączenie Gmaila są idempotentne oraz blokują nowe uruchomienia przed wyczyszczeniem lokalnego stanu.
- Testy domain/application używają fake Portów; adaptery mają testy kontraktowe/integracyjne z niepoufnymi fixture’ami.

### UX Design Requirements

Brak — MVP jest lokalnym projektem MCP/API-first bez niezależnego interfejsu graficznego.

### FR Coverage Map

FR-1: Epic 1 — lokalne OAuth tylko do odczytu i odłączenie konta.
FR-2: Epic 1 — zapis, podgląd i egzekwowanie Aktywnego Filtru Gmail.
FR-3: Epic 2 — thread-first Digest, deduplikacja i zakres przetwarzania.
FR-4: Epic 2 — walidowane Podsumowanie Wątku z priorytetem i działaniami.
FR-5: Epic 2 — lokalny Harmonogram i uczciwy status jego wykonania.
FR-6: Epic 3 — narzędzie MCP `get_daily_digest`.
FR-7: Epic 3 — potwierdzona analiza `summarize_gmail` przez lokalnie wybranego Dostawcę AI.
FR-8: Epic 3 — potwierdzone `compare_summaries` dla Wątku Aktywnego Filtru Gmail.
FR-9: Epic 1 — lokalna konfiguracja kluczy OpenAI i Claude oraz granice ich użycia.
FR-10: Epic 2 — minimalna retencja, automatyczne czyszczenie i ręczne usuwanie lokalnego stanu.

## Epic List

### Epic 1: Bezpieczne połączenie i kontrola skrzynki

Użytkownik łączy jedno konto Gmail, definiuje Aktywny Filtr Gmail i lokalnie konfiguruje dostawców AI, zachowując kontrolę nad zakresem danych.

**FRs covered:** FR-1, FR-2, FR-9

### Epic 2: Prywatna poranna odprawa z Gmaila

Użytkownik otrzymuje lokalny, automatyczny Digest nowych istotnych Wątków — z podsumowaniem, priorytetem i działaniami — bez utrwalania pełnej treści maili.

**FRs covered:** FR-3, FR-4, FR-5, FR-10

### Epic 3: Rozmowa z Gmailem przez MCP i porównanie modeli

Użytkownik pobiera Digest, uruchamia potwierdzoną analizę ad hoc przez MCP oraz świadomie porównuje OpenAI i Claude dla Wątku objętego Aktywnym Filtrem Gmail.

**FRs covered:** FR-6, FR-7, FR-8

## Epic 1: Bezpieczne połączenie i kontrola skrzynki

Użytkownik łączy jedno konto Gmail, definiuje Aktywny Filtr Gmail i lokalnie konfiguruje dostawców AI, zachowując kontrolę nad zakresem danych.

### Story 1.1: Przygotowanie lokalnego projektu i bezpiecznej konfiguracji

As a właściciel lokalnego narzędzia,
I want uruchomić projekt z walidowaną konfiguracją i prywatnym katalogiem danych,
So that mogę bezpiecznie dodać poświadczenia Gmaila oraz klucze AI bez ryzyka zapisania ich w repozytorium.

**Acceptance Criteria:**

**Given** świeży checkout projektu
**When** uruchamiam instalację przez `uv sync --locked`
**Then** projekt korzysta z Pythona 3.12 oraz zatwierdzonego `uv.lock`
**And** struktura źródeł zawiera `domain`, `application`, `adapters` i `bootstrap`.

**Given** lokalna konfiguracja
**When** aplikacja ładuje ustawienia
**Then** klucze OpenAI i Claude są odczytywane wyłącznie ze środowiska lub lokalnego `.env`
**And** brak wymaganego klucza zwraca czytelny błąd konfiguracji bez ujawniania sekretu.

**Given** uruchomienie aplikacji
**When** tworzony jest katalog danych użytkownika
**Then** katalog przechowuje token OAuth, SQLite i Digesty poza repozytorium
**And** `.env`, `credentials.json`, tokeny oraz dane aplikacji są ignorowane przez Git, a logi nie zawierają sekretów ani treści maili.

### Story 1.2: Połączenie i odłączenie konta Gmail przez OAuth

As a właściciel konta Gmail,
I want lokalnie połączyć lub odłączyć swoje konto przez OAuth,
So that aplikacja może bezpiecznie czytać tylko dozwolone wiadomości.

**Acceptance Criteria:**

**Given** poprawny lokalny plik `credentials.json` i brak ważnego tokenu
**When** uruchamiam polecenie połączenia Gmail
**Then** aplikacja otwiera lokalny przepływ OAuth w przeglądarce
**And** żąda wyłącznie zakresu `gmail.readonly`, bez hasła użytkownika.

**Given** pomyślna zgoda OAuth
**When** aplikacja odbiera kod zwrotny na lokalnym adresie
**Then** zapisuje token odświeżania wyłącznie w katalogu danych użytkownika
**And** pokazuje nazwę połączonego Konta Gmail.

**Given** nieważny, cofnięty lub zablokowany przez administratora token
**When** narzędzie potrzebuje dostępu do Gmaila
**Then** zwraca status `failed` z instrukcją ponownego połączenia
**And** nie zwraca pozornie kompletnego wyniku.

**Given** połączone konto
**When** uruchamiam odłączenie Gmail
**Then** nowe analizy są blokowane, lokalny token zostaje usunięty idempotentnie
**And** nie są usuwane żadne wiadomości w Gmailu.

### Story 1.3: Zarządzanie Aktywnym Filtrem Gmail i dostawcami AI

As a właściciel połączonego konta,
I want zapisać Aktywny Filtr Gmail oraz skonfigurować dostępnych dostawców AI,
So that kontroluję, które Wątki są analizowane i dokąd może trafić ich treść.

**Acceptance Criteria:**

**Given** połączone Konto Gmail
**When** zapisuję Filtr Gmail oparty na nadawcy, etykiecie lub słowach kluczowych
**Then** aplikacja pokazuje tekst filtru i liczbę pasujących Wątków przed zapisem
**And** domyślny filtr ogranicza się do Inboxa bez Promotions i Social.

**Given** poprawny Filtr Gmail
**When** zatwierdzam zapis
**Then** staje się on Aktywnym Filtrem Gmail
**And** kolejne uruchomienia Harmonogramu oraz `compare_summaries` są nim ograniczone.

**Given** filtr nieobsługiwany przez Gmail API
**When** próbuję go zapisać lub zastosować
**Then** otrzymuję `failed` z opisem problemu
**And** poprzedni Aktywny Filtr Gmail pozostaje bez zmian.

**Given** lokalne ustawienia dostawców
**When** konfiguruję klucze OpenAI i Claude
**Then** każdy skonfigurowany dostawca jest dostępny dla Digestu oraz `summarize_gmail`
**And** OpenAI jest ustawieniem domyślnym, a użytkownik może lokalnie wybrać OpenAI albo Claude dla Digestu i `summarize_gmail`, bez automatycznego fallbacku.

## Epic 2: Prywatna poranna odprawa z Gmaila

Użytkownik otrzymuje lokalny, automatyczny Digest nowych istotnych Wątków — z podsumowaniem, priorytetem i działaniami — bez utrwalania pełnej treści maili.

### Story 2.1: Lokalny stan analizy i deduplikacja Wątków

As a właściciel narzędzia,
I want aby aplikacja rozpoznawała nowe lub zmienione Wątki i prowadziła trwały stan analizy,
So that nie płacę ponownie za tę samą analizę ani nie otrzymuję niespójnych wyników.

**Acceptance Criteria:**

**Given** połączone Konto Gmail i Aktywny Filtr Gmail
**When** aplikacja wyszukuje kandydatów do analizy
**Then** pracuje na poziomie Wątku, a nie pojedynczej wiadomości
**And** uznaje Wątek za kwalifikujący się tylko po nowej wiadomości albo po rozpoczęciu spełniania Aktywnego Filtru Gmail.

**Given** rozpoczęcie analizy
**When** tworzony jest `AnalysisRun`
**Then** jego migawka wejścia i stan `running` są zapisywane lokalnie
**And** kandydaci są atomowo oznaczani pod blokadą jednego konta przed wywołaniem AI.

**Given** równoległe uruchomienie crona lub narzędzia MCP
**When** inne uruchomienie analizuje to samo konto
**Then** drugie uruchomienie nie tworzy duplikatu analizy tych samych Wątków
**And** wynik jest uczciwie oznaczony jako `complete`, `partial` albo `failed`.

**Given** niezmieniony wcześniej podsumowany Wątek
**When** uruchamiam analizę bez jawnego żądania ponownej analizy
**Then** aplikacja nie wysyła go ponownie do AI
**And** jawne żądanie ponownej analizy jest zapisane jako odrębne działanie.

### Story 2.2: Walidowane podsumowanie Wątku przez wybranego Dostawcę AI

As a właściciel narzędzia,
I want otrzymać krótkie i przewidywalne podsumowanie istotnego Wątku,
So that szybko rozpoznaję priorytet oraz działania bez ręcznego czytania całej korespondencji.

**Acceptance Criteria:**

**Given** Wątek zakwalifikowany do analizy
**When** aplikacja przygotowuje wejście dla lokalnie wybranego Dostawcy AI
**Then** usuwa załączniki, podpisy i zbędną cytowaną historię
**And** pełna treść Wątku nie jest zapisywana ani logowana.

**Given** poprawna odpowiedź wybranego Dostawcy AI
**When** adapter waliduje wynik
**Then** zapisuje `ThreadSummary` schema v1 ze streszczeniem do trzech zdań, priorytetem `wysoki`/`średni`/`niski`, działaniami, dostawcą i statusem
**And** brak działań jest zwracany jawnie bez wymyślania terminów ani właścicieli.

**Given** błąd API lub odpowiedź niezgodna ze schematem
**When** analiza Wątku nie może zostać poprawnie zakończona
**Then** Wątek i `AnalysisRun` dostają status `partial` albo `failed` z przyczyną
**And** aplikacja nie przełącza się automatycznie na drugiego dostawcę.

**Given** zapisane Podsumowanie Wątku
**When** jest prezentowane w Digescie lub późniejszym narzędziu MCP
**Then** zawiera link albo identyfikator źródłowego Wątku Gmail
**And** informuje, że wynik AI może być niepełny lub błędny.

### Story 2.3: Poranny Digest przez lokalny Harmonogram

As a właściciel konta Gmail,
I want otrzymywać lokalnie wygenerowany poranny Digest,
So that rozpoczynam dzień od najważniejszych nowych Wątków i działań.

**Acceptance Criteria:**

**Given** skonfigurowany Aktywny Filtr Gmail, Dostawca AI i stan analizy
**When** lokalny cron uruchamia zadanie o domyślnej godzinie 08:00 czasu lokalnego
**Then** wywołuje ten sam przypadek użycia co ręczna analiza
**And** użytkownik może zmienić godzinę lub wyłączyć Harmonogram w lokalnej konfiguracji.

**Given** udane uruchomienie Harmonogramu
**When** powstaje Digest
**Then** zawiera zakres czasu, czas wygenerowania, liczbę pasujących Wątków oraz pozycje z podsumowaniem, priorytetem, działaniami i uzasadnieniem uwzględnienia
**And** zapisuje status `complete` albo `partial`.

**Given** błąd OAuth, Gmail API, OpenAI lub crona
**When** Digest nie może powstać w całości
**Then** ostatni stan jest zapisany jako `failed` albo `partial` z przyczyną i kolejnym działaniem
**And** ręczne narzędzia MCP nadal mogą działać, jeśli ich zależności są dostępne.

**Given** zmiana konfiguracji dostawcy lub Harmonogramu
**When** następuje kolejne uruchomienie
**Then** używa ona nowych ustawień
**And** żadne działające uruchomienie nie zmienia dostawcy w trakcie analizy.

### Story 2.4: Retencja i ręczne usuwanie lokalnych danych

As a właściciel danych,
I want automatycznie usuwać stare wyniki i móc ręcznie wyczyścić lokalny stan,
So that ograniczam ryzyko prywatności bez dotykania poczty w Gmailu.

**Acceptance Criteria:**

**Given** lokalnie zapisane Digesty i Podsumowania Wątków
**When** uruchamia się czyszczenie retencji
**Then** usuwa wyniki starsze niż 30 dni
**And** nie usuwa wiadomości, etykiet ani innych danych w Gmailu.

**Given** uruchomiona analiza
**When** żądam ręcznego usunięcia danych
**Then** aplikacja blokuje nowe uruchomienia dla konta i kończy lub bezpiecznie oznacza aktywny `AnalysisRun`
**And** idempotentnie usuwa żądane lokalne Digesty, Podsumowania i — gdy wybrane — token OAuth.

**Given** wykonane usuwanie
**When** zapis jest potwierdzony użytkownikowi
**Then** log zawiera wyłącznie techniczny status operacji, bez treści Wątków lub sekretów
**And** kolejna analiza po usunięciu wymaga ponownego spełnienia normalnych warunków dostępu i deduplikacji.

## Epic 3: Rozmowa z Gmailem przez MCP i porównanie modeli

Użytkownik pobiera Digest, uruchamia potwierdzoną analizę ad hoc przez MCP oraz świadomie porównuje OpenAI i Claude dla Wątku objętego Aktywnym Filtrem Gmail.

### Story 3.1: Lokalny serwer FastMCP i odczyt Digestu

As a użytkownik klienta MCP,
I want lokalnie odkryć serwer Gmail MCP i pobrać ostatni Digest,
So that wykorzystuję wyniki analizy w rozmowie z klientem MCP bez wystawiania usługi do sieci.

**Acceptance Criteria:**

**Given** zainstalowany lokalny projekt i zapisany Digest
**When** uruchamiam serwer przez transport `stdio`
**Then** klient MCP może odkryć dokładnie trzy narzędzia: `get_daily_digest`, `summarize_gmail` i `compare_summaries`
**And** serwer nie otwiera endpointu HTTP ani nie oferuje narzędzi modyfikujących Gmaila.

**Given** istniejący ostatni Digest
**When** klient wywołuje `get_daily_digest`
**Then** otrzymuje `status`, zakres czasu, czas wygenerowania, liczbę Wątków i pozycje Digestu
**And** każda pozycja wskazuje źródłowy Wątek Gmail oraz faktycznie użytego Dostawcę AI.

**Given** brak Digestu albo nieudane ostatnie uruchomienie
**When** klient wywołuje `get_daily_digest`
**Then** otrzymuje `failed` albo `partial` z przyczyną i proponowanym kolejnym działaniem
**And** odpowiedź zachowuje jednolity envelope `status`, `data`, `reason`.

### Story 3.2: Potwierdzona analiza ad hoc przez wybranego dostawcę

As a użytkownik klienta MCP,
I want zobaczyć dokładny zakres jednorazowej analizy i świadomie go potwierdzić,
So that używam OpenAI lub Claude do nowych pytań o Gmail bez przypadkowego ujawniania dodatkowych danych.

**Acceptance Criteria:**

**Given** Aktywny Filtr Gmail albo filtr jednorazowy podany w `summarize_gmail`
**When** narzędzie przygotowuje podgląd
**Then** pokazuje rozwiązany Filtr Gmail, kolejność i liczbę Wątków oraz lokalnie wybranego Dostawcę AI
**And** filtr jednorazowy nie zmienia Aktywnego Filtru Gmail.

**Given** zaakceptowany podgląd
**When** aplikacja tworzy potwierdzenie
**Then** tworzy krótkotrwały, jednorazowy token związany z operacją, hashem filtra, migawką Wątków, dostawcą i hashem oczyszczonego wejścia
**And** wykonanie bez ważnego tokenu nie pobiera treści z Gmaila ani nie wywołuje AI.

**Given** ważne potwierdzenie
**When** klient wykonuje `summarize_gmail`
**Then** aplikacja analizuje wyłącznie potwierdzoną migawkę przez lokalnie wybranego Dostawcę AI
**And** zwraca `ThreadSummary` oraz status `complete`, `partial` albo `failed`.

**Given** wygasły lub niezgodny token potwierdzenia
**When** klient próbuje uruchomić analizę
**Then** narzędzie zwraca `failed` z instrukcją odświeżenia podglądu
**And** nie rozszerza zakresu ani nie wykonuje ukrytego fallbacku dostawcy.

### Story 3.3: Świadome porównanie OpenAI i Claude

As a użytkownik budujący demonstrację GenAI,
I want porównać podsumowania OpenAI i Claude dla jednego dozwolonego Wątku,
So that oceniam różnice modeli bez automatycznego mnożenia kosztów lub rozszerzania zakresu danych.

**Acceptance Criteria:**

**Given** Wątek objęty Aktywnym Filtrem Gmail
**When** klient wywołuje `compare_summaries`
**Then** narzędzie sprawdza zgodność Wątku z Aktywnym Filtrem Gmail
**And** Wątek spoza filtru zwraca `failed` bez pobierania jego treści ani wywoływania AI.

**Given** poprawny Wątek i podgląd porównania
**When** użytkownik potwierdza wysłanie treści do obu dostawców
**Then** token potwierdzenia wiąże ten sam oczyszczony `AnalysisInput` z OpenAI i Claude
**And** oba modele otrzymują identyczną migawkę Wątku.

**Given** odpowiedzi obu dostawców
**When** `compare_summaries` kończy pracę
**Then** zwraca dwa `ThreadSummary` w schema v1 oraz osobny Status Wyniku dla każdego dostawcy
**And** wynik pokazuje, który dostawca wygenerował każde podsumowanie.

**Given** błąd jednego dostawcy
**When** drugi dostawca zwraca poprawny wynik
**Then** narzędzie zwraca `partial` wraz z wynikiem poprawnego dostawcy i przyczyną błędu drugiego
**And** nie zastępuje żadnego wyniku automatyczną dodatkową próbą ani fallbackiem.
