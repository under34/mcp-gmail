# PRD Quality Review — Usługa MCP dla Gmaila

## Overall verdict

To jest spójny i uczciwie ograniczony PRD dla lokalnego demonstratora: decyzje o jednym koncie, odczycie, jawnej zgodzie na wysłanie treści i granicach MVP są konkretne, a większość FR ma testowalne skutki. Nie jest jeszcze w pełni gotowy do budowania bez doprecyzowania, jak rozpoznać i ocenić „najważniejszy” Wątek — centralną obietnicę produktu — oraz czym dokładnie jest aktywny Filtr Gmail w przepływie narzędzi MCP.

## Decision-readiness — adequate

PRD jasno rozstrzyga najważniejsze kompromisy: lokalny, jednoosobowy demonstrator zamiast SaaS (§0, §2.2), OAuth z `gmail.readonly` (§4.1, FR-1), brak mutacji Gmaila (§6) i Claude wyłącznie przy świadomym porównaniu (§4.3, FR-8). Odroczenia w §7.2 mówią zarówno co wypada z MVP, jak i dlaczego. §9 nie maskuje nierozstrzygniętych pytań jako pytań otwartych; przy tej skali brak takich pytań jest wiarygodny.

Jedna operacyjna decyzja pozostaje jednak domyślna tylko z nazwy: narzędzia odwołują się do „aktywnego Filtru Gmail”, ale PRD nie rozstrzyga, jak użytkownik go ustala lub zmienia w sesji MCP.

### Findings

- **medium** Nieustalony właściciel i cykl życia aktywnego Filtru Gmail (§4.1, FR-2; §4.3, FR-8) — FR-2 pozwala definiować i zmieniać Filtr Gmail, natomiast FR-8 wymaga, by Wątek należał do „aktywnego” Filtru Gmail. Nie wiadomo, czy jest to filtr domyślny, ostatnio zapisany, parametr wywołania, czy konfiguracja narzędzia; decyzja wpływa na kontrolę danych. *Fix:* zdefiniuj źródło aktywnego filtru, jego zasięg (wywołanie/sesja/konfiguracja), zachowanie po zmianie oraz sposób ujawnienia go klientowi MCP.

## Substance over theater — strong

Wizja jest rozpoznawalnie własna dla tego produktu: „Poranna odprawa z Gmaila przez MCP” łączy ograniczony zakres skrzynki, Digest i pytania przez MCP (§1), a nie obiecuje ogólnego asystenta pocztowego. Trzy UJ-y mają odrębne konsekwencje dla produktu: codzienny odczyt, analizę na żądanie i świadome porównanie dostawców (§2.3). NFR-y oraz cele negatywne wynikają z rzeczywistych ryzyk poczty i zewnętrznego GenAI, zwłaszcza braku zapisu, retencji i zgody na przesłanie treści (§5–§6).

## Strategic coherence — thin

Teza jest spójna: użytkownik ma szybciej rozpoznać nowe istotne wątki, zachowując kontrolę nad zakresem danych (§1). MVP logicznie ją wspiera, a SM-C1 jest właściwą kontrmetryką przeciw sztucznemu zwiększaniu liczby analizowanych wątków (§8). Zakres jest przy tym uczciwie problem-solving, nie udaje platformy.

PRD nie definiuje jednak, kiedy priorytet nadany przez model jest trafny ani w jaki sposób demonstracja potwierdzi skrócenie rozpoznania skrzynki. SM-1 mierzy poprawność procesu przez pięć poranków, ale nie waliduje centralnej wartości Digestu.

### Findings

- **high** Brak miernika jakości priorytetu i wartości „porannej odprawy” (§1; §4.2, FR-4; §8, SM-1) — skala `niski`/`średni`/`wysoki` jest tylko etykietą; PRD nie podaje kryteriów trafności ani sposobu sprawdzenia, czy Digest wskazał właściwe Wątki. Pięć poprawnych technicznie uruchomień może więc spełnić SM-1 mimo bezużytecznych priorytetów. *Fix:* dodaj mały, ręcznie oznaczony zestaw demonstracyjnych Wątków i kryterium akceptacji jakości (np. wymaganą zgodność priorytetów lub brak pominięcia oznaczonych pilnych wątków), plus prostą miarę czasu/liczby wątków potrzebnych do porannego rozpoznania.

## Done-ness clarity — adequate

FR-1–FR-10 mają zwykle jednoznaczne, obserwowalne konsekwencje: scope OAuth, zachowanie nieprawidłowego filtru, zawartość Digestu, osobne statusy porównania i zakaz zapisu są możliwe do przetestowania (§4). FR-10 podaje konkretne granice retencji: brak trwałej pełnej treści oraz automatyczne usuwanie po 30 dniach. To jest wystarczająco dobry fundament do historii implementacyjnych.

Niedookreślone są dwa kluczowe kontrakty: semantyka priorytetu/działań w Podsumowaniu Wątku oraz znaczenie „zmienionego” Wątku dla deduplikacji. Bez nich różne implementacje mogą spełnić tekst FR, a zwracać istotnie inne wyniki i koszty API.

### Findings

- **medium** Kontrakt Podsumowania Wątku nie określa znaczenia wyniku (§4.2, FR-4) — FR-4 wymaga „krótkiego streszczenia, priorytetu i listy działań”, lecz nie definiuje kryteriów skali priorytetu, minimalnego schematu działania (np. właściciel/termin) ani zasad, kiedy działanie ma zostać zwrócone. To uniemożliwia obiektywny test poza obecnością pól. *Fix:* określ schemat wyniku oraz krótką rubrykę klasyfikacji priorytetu i działań, w tym zachowanie dla niepewności.

- **low** „Nowy lub zmieniony” Wątek nie ma obserwowalnej definicji (§4.2, FR-3; §5, NFR-4) — PRD wiąże z tym warunek ponownej analizy i koszt, lecz nie mówi, czy zmianą jest nowa wiadomość, etykieta, metadane czy tylko treść, ani jak traktować zmianę filtru. *Fix:* podaj sygnał Gmail/API używany do wykrywania zmiany oraz zachowanie cache’u po zmianie filtru lub ręcznym uruchomieniu.

## Scope honesty — strong

Ograniczenia są wyłożone wprost, a nie domyślne: §6 wyklucza modyfikacje Gmaila, załączniki, retencję pełnej treści i automatyzację odpowiedzi; §7.2 wyklucza hosting, wielokontowość i integracje organizacyjne wraz z powodami. Decyzje wymagające prywatności są częścią FR-7–FR-10, nie ukrytym szczegółem architektury. Brak tagów `[ASSUMPTION]` i `[NOTE FOR PM]` jest uzasadniony: dokument nie opiera kluczowego działania na oznaczonych jako tymczasowe ustaleniach, a §9 uczciwie stwierdza brak pytań blokujących.

## Downstream usability — adequate

Słownik stabilizuje podstawowe rzeczowniki domenowe (§3), identyfikatory FR-1–FR-10 są ciągłe i unikalne, a wszystkie trzy UJ-y mają nazwanego protagonistę Under (§2.3). SM-1 i SM-2 odwołują się do istniejących FR, dzięki czemu artefakty następcze mogą łatwo śledzić znaczną część zakresu.

Pojęcie „aktywnego Filtru Gmail” pojawia się jednak poza definicją słownika, a brak kontraktu semantycznego Podsumowania Wątku zostawia architekturze i historiom istotne decyzje produktowe. Nie blokuje to ekstrakcji, ale obniża jej jednoznaczność.

## Shape fit — strong

Kształt dokumentu odpowiada hobbystycznemu demonstratorowi, który ma zasilać architekturę, epiki i historie (§0). UJ-y są nieliczne i konieczne dla trzech odmiennych ścieżek interakcji; nie są personowym formalizmem dla jednoosobowego produktu. Poziom rygoru w prywatności, OAuth i statusach wyników jest proporcjonalny do integracji z pocztą, mimo że produkt pozostaje lokalny i mały.

## Mechanical notes

Brak `addendum.md`. FR-1–FR-10 są ciągłe, niepowtórzone, a wszystkie referencje FR w SM-1 i SM-2 rozwiązują się. UJ-1–UJ-3 są ciągłe i każdy ma protagonstę. Słownik jest ogólnie spójny, ale „aktywny Filtr Gmail” z FR-8 nie jest zdefiniowanym terminem i powinien zostać dodany lub zastąpiony zdefiniowaną nazwą. Brak inline tagów `[ASSUMPTION]` oznacza, że Indeks założeń „Brak aktywnych założeń” prawidłowo się domyka; §9 nie zawiera pytań wymagających roundtripu.
