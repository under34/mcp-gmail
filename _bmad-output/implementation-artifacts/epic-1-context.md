# Epic 1 Context: Bezpieczne połączenie i kontrola skrzynki

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Ten epik ustanawia lokalną, prywatną granicę dostępu do kont Gmail: jedno konto jest aktywne naraz, jego filtr jest trwały i odseparowany od pozostałych profili, a użytkownik świadomie wybiera skonfigurowanego dostawcę AI.

## Stories

- Story 1.1: Przygotowanie lokalnego projektu i bezpiecznej konfiguracji
- Story 1.2: Połączenie i odłączenie konta Gmail przez OAuth
- Story 1.3: Zarządzanie Aktywnym Filtrem Gmail i dostawcami AI

## Requirements & Constraints

- Produkt jest lokalnym MVP dla wielu prywatnych profili Gmail, z jednym aktywnym kontem naraz; Gmail pozostaje wyłącznie do odczytu. Nie wolno wysyłać, usuwać, archiwizować, oznaczać ani w inny sposób modyfikować wiadomości.
- OAuth żąda tylko zakresu `gmail.readonly`. Pomyślne połączenie ujawnia połączone konto; token nieważny, cofnięty lub zablokowany musi dać jawny wynik `failed` z instrukcją ponownego połączenia, nigdy pozorny sukces.
- Odłączenie blokuje nowe analizy i idempotentnie usuwa lokalny token, bez zmian w Gmailu.
- Filtr Gmail jest jawnym kryterium opartym na nadawcy, etykiecie lub słowach kluczowych. Domyślny filtr obejmuje Inbox i wyklucza Promotions oraz Social.
- Przed zapisem filtra należy pokazać jego tekst oraz liczbę pasujących Wątków. Tylko poprawnie obsługiwany filtr może zastąpić Aktywny Filtr Gmail; błąd nie może zmienić poprzednio zapisanego zakresu ani rozszerzyć analizy.
- Aktywny Filtr Gmail ogranicza późniejszy Harmonogram i `compare_summaries`; jednorazowe filtry użyte później do `summarize_gmail` go nie modyfikują.
- OpenAI jest domyślnym dostawcą. Dla Digestu i `summarize_gmail` użytkownik lokalnie wybiera OpenAI albo Claude, wyłącznie spośród dostawców z poprawnie skonfigurowanym kluczem. Brak wymaganego klucza zwraca `failed` z instrukcją konfiguracji.
- Nie stosować automatycznego fallbacku ani automatycznego wyboru dostawcy. Treść Wątku nie może trafić do innego dostawcy niż wybrany; wyjątkiem jest późniejsze, osobno potwierdzone `compare_summaries`.
- Klucze AI pochodzą wyłącznie ze środowiska procesu lub lokalnego `.env`. Token OAuth, przyszła baza SQLite i Digesty pozostają w katalogu danych bieżącego użytkownika, poza repozytorium. Sekrety, treści maili i załączniki nie mogą trafiać do Git ani logów.

## Technical Decisions

- Zachować architekturę hexagonalną: `domain` przechowuje zwalidowane wartości bez importów SDK; `application` definiuje przypadki użycia i Porty; `adapters` integrują Gmail oraz pliki lokalne; wyłącznie `bootstrap` ładuje ustawienia i składa zależności.
- Konfigurację ładować jednokrotnie w `bootstrap`; żaden moduł nie odczytuje zmiennych środowiskowych bezpośrednio. Błędy zewnętrzne adapterów należy tłumaczyć na typowane błędy aplikacyjne.
- GmailAdapter pracuje na Wątkach, nie pojedynczych wiadomościach, i egzekwuje `gmail.readonly`. Walidacja oraz podgląd filtra muszą korzystać z tego samego semantycznego zakresu, który zostanie zapisany.
- Stosować konwencje: encje domenowe w pojedynczej liczbie PascalCase, Porty z sufiksem `Port`, implementacje z sufiksem `Adapter`, przypadki użycia jako czasownikowe nazwy; identyfikatory są nieprzezroczystymi stringami, czas UTC ISO 8601.
- Testy domain/application używają fake Portów; GmailAdapter wymaga testów kontraktowych lub integracyjnych z niepoufnymi fixture’ami. Nie wprowadzać jeszcze zdalnego transportu ani dodatkowych powierzchni API.

## Cross-Story Dependencies

- Story 1.1 dostarcza walidowaną konfigurację, katalog danych i granicę sekretów wymagane przez OAuth, zapis filtra oraz konfigurację dostawców.
- Story 1.2 dostarcza połączone konto i GmailAdapter potrzebne do podglądu oraz zapisu Aktywnego Filtru w Story 1.3.
- Story 1.3 jest warunkiem dla Epiku 2: Harmonogram i Digest używają zapisanego filtra oraz wybranego dostawcy. Jest też warunkiem dla Epiku 3, gdzie filtr ogranicza porównanie modeli, a wybór dostawcy steruje analizą ad hoc.
