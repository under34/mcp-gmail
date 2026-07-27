---
title: "PRD: Usługa MCP dla Gmaila"
status: final
created: 2026-07-27
updated: 2026-07-27
---

# PRD: Usługa MCP dla Gmaila

## 0. Cel dokumentu

Ten PRD definiuje hobbystyczny demonstrator dla właściciela jednego konta Gmail. Jest przeznaczony dla osoby implementującej kolejne artefakty BMad: architekturę, epiki i historie. Opiera się na [briefie produktu](../../briefs/brief-under_34@o2.pl-2026-07-27/brief.md); opisuje zachowanie i granice produktu, a nie wybór frameworka, transportu MCP ani modelu bazy danych.

## 1. Wizja

Usługa MCP dla Gmaila ma skrócić poranne rozpoznanie skrzynki: z nowych, istotnych wątków tworzy digest z priorytetami i działaniami, a następnie pozwala dopytać o wybrany zakres przez klienta MCP. Jednocześnie projekt jest demonstratorem portfolio pokazującym integrację OAuth 2.0 i Gmail API, serwera MCP oraz zewnętrznych modeli GenAI.

Demonstracja „Poranna odprawa z Gmaila przez MCP” obejmuje połączenie jednego konta przez OAuth, jawne ograniczenie zakresu wiadomości, utworzenie digestu oraz zapytanie MCP o istotne wątki. Dla świadomie wybranego wątku użytkownik może porównać wynik OpenAI i Claude. System nie zmienia wiadomości ani nie wysyła danych do drugiego dostawcy bez wyraźnego polecenia.

## 2. Użytkownik

### 2.1 Zadania użytkownika

- Jako właściciel jednego konta Gmail chcę rano zobaczyć najważniejsze nowe wątki i działania, aby szybciej rozpocząć pracę.
- Jako osoba budująca portfolio chcę pokazać działający przepływ Gmail OAuth → MCP → GenAI → ustrukturyzowany wynik, aby wiarygodnie zademonstrować praktyczne kompetencje.
- Jako osoba dbająca o prywatność chcę samodzielnie ograniczyć zakres wiadomości i dostawcę AI, aby zachować kontrolę nad danymi.

### 2.2 Poza grupą użytkowników v1

- Wiele kont, wielu użytkowników i publiczna usługa SaaS.
- Osoby oczekujące automatycznego wysyłania odpowiedzi, archiwizacji lub innych zmian w Gmailu.

### 2.3 Kluczowe scenariusze

- **UJ-1. Under wykonuje poranną odprawę.** Po lokalnym połączeniu Konta Gmail przez OAuth system zgodnie z Harmonogramem tworzy Digest. Under wywołuje `get_daily_digest` w kliencie MCP, widzi zakres czasu, liczbę Wątków i ich priorytety, a następnie otwiera oryginalny Wątek przez link Gmail.
- **UJ-2. Under analizuje określony zakres.** W kliencie MCP podaje Filtr Gmail i Dostawcę AI. `summarize_gmail` pokazuje rozwiązany zakres przed pobraniem treści; po potwierdzeniu zwraca Podsumowania Wątków i jawny Status Wyniku.
- **UJ-3. Under porównuje modele.** Dla świadomie wybranego Wątku uruchamia `compare_summaries`, wybiera OpenAI i Claude oraz otrzymuje dwa wyniki w tym samym formacie. Brak automatycznego przełączania lub równoległego porównywania wszystkich wiadomości.

## 3. Słownik

- **Konto Gmail** — pojedyncze konto Google połączone lokalnie przez OAuth wyłącznie do odczytu.
- **Wątek** — rozmowa Gmail prezentowana jako jedna pozycja analizy, nawet gdy zawiera wiele wiadomości.
- **Filtr Gmail** — jawne kryterium określające, które Wątki mogą zostać pobrane; może zawierać nadawcę, etykietę lub słowa kluczowe.
- **Aktywny Filtr Gmail** — ostatni Filtr Gmail zapisany lokalnie; ogranicza Harmonogram i `compare_summaries`.
- **Digest** — zapisany lokalnie wynik porannej analizy obejmujący Wątki z określonego zakresu czasu.
- **Podsumowanie Wątku** — ustrukturyzowany wynik dla Wątku: streszczenie, priorytet i działania.
- **Dostawca AI** — zewnętrzny dostawca analizy: OpenAI jest domyślny, a użytkownik może lokalnie wybrać OpenAI albo Claude dla Digestu i `summarize_gmail`; `compare_summaries` używa obu dostawców.
- **Status Wyniku** — stan `complete`, `partial` lub `failed`, opisujący kompletność operacji.
- **Harmonogram** — lokalne, cykliczne uruchamianie tworzenia Digestu.

## 4. Funkcje

### 4.1 Połączenie Konta Gmail i kontrola zakresu

**Opis:** Użytkownik łączy jedno Konto Gmail przez OAuth 2.0 z zakresem tylko do odczytu. Przed analizą definiuje Filtr Gmail; domyślna konfiguracja obejmuje Inbox bez kategorii Promotions i Social. Funkcja realizuje UJ-1 i UJ-2.

#### FR-1: Autoryzacja tylko do odczytu

Użytkownik może połączyć jedno Konto Gmail przez ekran zgody OAuth, bez podawania hasła aplikacji.

**Konsekwencje testowalne:**
- System żąda wyłącznie zakresu `gmail.readonly`.
- System pokazuje nazwę połączonego Konta Gmail oraz umożliwia lokalne odłączenie i usunięcie tokenów.
- Gdy zgoda, token lub dostęp administracyjny jest nieważny, system zwraca `failed` z instrukcją ponownego połączenia; nie zwraca pozornie kompletnego wyniku.

#### FR-2: Jawne Filtry Gmail

Użytkownik może zdefiniować i zmienić Filtr Gmail według nadawcy, etykiety lub słów kluczowych.

**Konsekwencje testowalne:**
- Domyślny Filtr Gmail ogranicza się do Inboxa i wyklucza Promotions oraz Social.
- Przed zapisaniem Filtru Gmail użytkownik może zobaczyć jego tekst oraz liczbę pasujących Wątków.
- Ostatni zapisany Filtr Gmail staje się Aktywnym Filtrem Gmail; jego zmiana jest widoczna przed kolejną analizą.
- Gdy Filtr Gmail nie jest obsługiwany przez Gmail API, system zwraca `failed` z opisem problemu i nie uruchamia analizy poza zamierzonym zakresem.

### 4.2 Generowanie Digestu i Podsumowań Wątków

**Opis:** Harmonogram raz dziennie o 08:00 czasu lokalnego analizuje tylko nowe lub zmienione Wątki spełniające Aktywny Filtr Gmail. Dla każdego tworzy Podsumowanie Wątku z użyciem lokalnie wybranego Dostawcy AI; OpenAI jest ustawieniem domyślnym. Funkcja realizuje UJ-1 i UJ-2.

#### FR-3: Przetwarzanie nowych lub zmienionych Wątków

System tworzy Digest tylko dla Wątków, które od poprzedniego udanego Digestu zawierają nową wiadomość albo zaczęły spełniać Aktywny Filtr Gmail.

**Konsekwencje testowalne:**
- Digest zawiera zakres czasu, liczbę pasujących Wątków oraz czas wygenerowania.
- System nie analizuje ponownie Wątku, który nie zawiera nowej wiadomości i nadal spełnia Aktywny Filtr Gmail.
- Ręczne uruchomienie nie omija deduplikacji, chyba że użytkownik jawnie zażąda ponownej analizy.
- Każda pozycja Digestu zawiera link lub identyfikator prowadzący do oryginalnego Wątku Gmail oraz wskazanie, dlaczego została uwzględniona.

#### FR-4: Ustrukturyzowane Podsumowanie Wątku

System zwraca dla każdego analizowanego Wątku krótkie streszczenie, priorytet i listę działań.

**Konsekwencje testowalne:**
- Streszczenie ma najwyżej trzy zdania; priorytet używa stałej skali: `wysoki` dla szybkiego działania lub decyzji, `średni` dla sprawy wymagającej uwagi bez pilności, `niski` dla informacji.
- Działania są krótką listą konkretnych czynności albo jawnym brakiem działań; system nie wymyśla terminów ani właścicieli działań.
- System wskazuje, że Podsumowanie Wątku może być niepełne lub błędne i prowadzi do źródłowego Wątku.

#### FR-5: Lokalny Harmonogram

Użytkownik może włączyć, wyłączyć i skonfigurować poranny Harmonogram Digestu.

**Konsekwencje testowalne:**
- Harmonogram jest wykonywany lokalnie o 08:00 czasu lokalnego; użytkownik może zmienić godzinę w lokalnej konfiguracji, a brak jego uruchomienia nie blokuje ręcznych narzędzi MCP.
- Harmonogram używa zapisanego Dostawcy AI; OpenAI jest ustawieniem domyślnym, a zmiana lokalnej konfiguracji dostawcy działa od następnego uruchomienia.
- Nieudane uruchomienie jest widoczne przy następnym odczycie Digestu jako `failed` albo `partial` wraz z przyczyną.

### 4.3 Narzędzia MCP

**Opis:** Serwer udostępnia tylko narzędzia odczytu. Klient MCP może odkryć ich opis, przesłać jawne parametry i otrzymać wynik ze Statusem Wyniku. Funkcja realizuje wszystkie scenariusze.

#### FR-6: `get_daily_digest`

Klient MCP może pobrać ostatni Digest.

**Konsekwencje testowalne:**
- Wynik zawiera Status Wyniku, zakres czasu, czas wygenerowania i liczbę Wątków.
- Gdy Digest nie istnieje, wynik zwraca `failed` z instrukcją uruchomienia analizy lub sprawdzenia Harmonogramu.

#### FR-7: `summarize_gmail`

Klient MCP może zainicjować analizę przez lokalnie wybranego Dostawcę AI dla Aktywnego Filtru Gmail albo dla jawnego Filtru Gmail użytego jednorazowo.

**Konsekwencje testowalne:**
- Narzędzie przedstawia rozwiązany Filtr Gmail i wymaga potwierdzenia użytkownika przed pobraniem pełnej treści Wątków; jednorazowy Filtr Gmail nie zmienia Aktywnego Filtru Gmail.
- Wynik zawiera Podsumowania Wątków, faktycznie użytego Dostawcę AI oraz Status Wyniku.
- Narzędzie nie wykonuje żadnej operacji zapisu, wysyłki ani usunięcia w Gmailu.

#### FR-8: `compare_summaries`

Klient MCP może porównać Podsumowanie Wątku utworzone przez OpenAI i Claude dla jednoznacznie wskazanego Wątku objętego Aktywnym Filtrem Gmail.

**Konsekwencje testowalne:**
- Narzędzie wymaga jawnego identyfikatora Wątku, sprawdza zgodność z Aktywnym Filtrem Gmail i wymaga jawnego potwierdzenia wysłania jego treści do obu Dostawców AI.
- Wątek spoza Aktywnego Filtru Gmail zwraca `failed` bez wysłania jego treści do Dostawcy AI.
- Wynik zwraca oba Podsumowania Wątków w tym samym schemacie oraz osobny Status Wyniku dla każdego dostawcy.
- Błąd jednego Dostawcy AI nie powoduje automatycznego użycia drugiego ani ukrycia błędu.

### 4.4 Wybór Dostawcy AI i kontrola danych

**Opis:** OpenAI jest domyślnym Dostawcą AI. Użytkownik może lokalnie wybrać OpenAI albo Claude dla Digestu i `summarize_gmail`; `compare_summaries` używa obu po jawnym potwierdzeniu. Użytkownik sam konfiguruje klucze i decyduje, dokąd trafia treść. Funkcja realizuje UJ-2 i UJ-3.

#### FR-9: Jawny wybór Dostawcy AI

Użytkownik może skonfigurować lokalny klucz OpenAI i Claude oraz lokalnie wybrać Dostawcę AI dla Digestu i `summarize_gmail`.

**Konsekwencje testowalne:**
- Brak wymaganego klucza Dostawcy AI zwraca `failed` z instrukcją konfiguracji.
- System nie wysyła treści Wątku do Dostawcy AI innego niż lokalnie wybrany, z wyjątkiem jawnie potwierdzonego `compare_summaries`.
- OpenAI jest ustawieniem domyślnym; Digest i `summarize_gmail` używają lokalnie wybranego Dostawcy AI wyłącznie po konfiguracji jego klucza.

#### FR-10: Minimalna retencja danych

System zapisuje lokalnie tylko identyfikatory Gmaila, hashe, metadane i Podsumowania Wątków potrzebne do działania Digestu.

**Konsekwencje testowalne:**
- System nie utrwala ani nie loguje pełnej treści Wątków lub załączników.
- System automatycznie usuwa Digesty i Podsumowania Wątków po 30 dniach.
- Użytkownik może usunąć lokalne zapisane wyniki i tokeny OAuth.
- Każda operacja analizy pokazuje wybranego Dostawcę AI przed wysłaniem treści.

## 5. Przekrojowe wymagania jakościowe

- **NFR-1 — Prywatność:** system przetwarza treść Wątku wyłącznie w celu utworzenia żądanego Podsumowania Wątku lub Digestu; nie wykorzystuje jej do innych celów.
- **NFR-2 — Wiarygodność:** każde narzędzie MCP zwraca Status Wyniku `complete`, `partial` albo `failed` z czytelną przyczyną i następnym działaniem.
- **NFR-3 — Kontrola użytkownika:** system nie rozszerza Aktywnego Filtru Gmail, nie wykonuje zapisu w Gmailu i nie zmienia Dostawcy AI bez lokalnej, jawnej konfiguracji użytkownika; `compare_summaries` wymaga osobnego potwierdzenia wysłania treści do obu dostawców.
- **NFR-4 — Koszt:** system ogranicza wywołania Gmail API i Dostawcy AI do nowych lub zmienionych Wątków; nie analizuje ponownie niezmienionych danych bez ręcznego polecenia.
- **NFR-5 — Lokalność:** tokeny OAuth, klucze Dostawców AI i zapisane wyniki są przechowywane lokalnie na komputerze użytkownika.

## 6. Cele negatywne

- Produkt v1 nie jest publiczną usługą ani narzędziem dla wielu kont.
- Produkt v1 nie zapisuje, nie wysyła, nie usuwa, nie archiwizuje ani nie oznacza wiadomości Gmail.
- Produkt v1 nie przetwarza załączników i nie przechowuje pełnych treści Wątków.
- Produkt v1 nie automatyzuje odpowiedzi, wydobywania terminów ani wyboru Dostawcy AI.

## 7. Zakres MVP

### 7.1 W zakresie

- Lokalne OAuth i jedno Konto Gmail z `gmail.readonly`.
- Konfigurowalny Filtr Gmail, poranny Harmonogram i lokalny Digest.
- Podsumowania Wątków z priorytetem i działaniami.
- Trzy narzędzia MCP: `get_daily_digest`, `summarize_gmail`, `compare_summaries`.
- OpenAI jako domyślny Dostawca AI; lokalny wybór OpenAI albo Claude dla Digestu i `summarize_gmail`; oba modele w ręcznie wywołanym `compare_summaries`.
- Jawne statusy błędów, częściowych wyników i kompletności.

### 7.2 Poza zakresem MVP

- Hosting zdalny i działanie niezależne od lokalnego komputera — odroczone po walidacji MVP.
- Wysyłanie Digestu e-mailem — odroczone, aby uniknąć pętli i dodatkowego zakresu integracji.
- Wielu użytkowników, wiele kont i integracje organizacyjne — odroczone z powodu OAuth, prywatności i bezpieczeństwa.

## 8. Metryki sukcesu

- **SM-1:** przez pięć kolejnych poranków Digest obejmuje wyłącznie Wątki pasujące do Aktywnego Filtru Gmail, pokazuje ich priorytety i działania oraz nie wymaga ponownej analizy niezmienionego Wątku. Weryfikuje FR-2, FR-3, FR-4 i FR-5.
- **SM-2:** na ręcznie oznaczonym zestawie co najmniej 10 Wątków system nie pomija żadnego Wątku oznaczonego przez użytkownika jako `wysoki`, a co najmniej 80% priorytetów zgadza się z oznaczeniem użytkownika. Weryfikuje FR-4.
- **SM-3:** demonstracja obejmuje pomyślne użycie wszystkich trzech narzędzi MCP, w tym jawne potwierdzenie przed `summarize_gmail` i `compare_summaries`, oraz widoczny Status Wyniku. Weryfikuje FR-6, FR-7, FR-8, FR-9 i FR-10.
- **SM-C1:** liczba analizowanych Wątków nie jest celem samym w sobie; system nie może zwiększać jej kosztem rozszerzenia Aktywnego Filtru Gmail lub ponownego przetwarzania niezmienionych Wątków.

## 9. Otwarte pytania

Brak otwartych pytań blokujących MVP.

## 10. Indeks założeń

Brak aktywnych założeń wymagających potwierdzenia.
