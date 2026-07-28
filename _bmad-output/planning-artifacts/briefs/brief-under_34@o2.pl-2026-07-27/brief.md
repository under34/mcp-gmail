---
title: "Product Brief: Usługa MCP dla Gmaila"
status: ready-for-review
created: 2026-07-27
updated: 2026-07-27
---

# Product Brief: Usługa MCP dla Gmaila

## Podsumowanie

Lokalna usługa MCP dla prywatnych kont Gmail automatyzuje poranną odprawę z nowych, istotnych wiadomości. Jedno konto jest aktywne naraz, a jego filtr i lokalne wyniki są odseparowane od pozostałych kont. Usługa pobiera tylko wiadomości zgodne z konfigurowalnymi filtrami, tworzy ich zwięzłe podsumowania z priorytetem i działaniami, a wyniki udostępnia przez narzędzia MCP.

MVP działa lokalnie, przetwarza tylko nowe lub zmienione maile i nie utrwala ich pełnej treści. OpenAI API jest domyślnym dostawcą AI, a Anthropic Claude API — ręcznie wybieraną alternatywą porównawczą.

## Użytkownik i wartość

Pierwszym użytkownikiem jest właściciel prywatnych kont Gmail, który chce szybko wiedzieć, które nowe wiadomości są ważne i co z nich wynika. Sukces MVP oznacza, że poranny digest wiarygodnie przedstawia najważniejsze nowe maile oraz wynikające z nich działania dla aktywnego konta.

## Problem

Ważne wiadomości, decyzje i zadania giną w codziennym napływie e-maili. Ręczne przeglądanie Inboxa zajmuje czas i utrudnia rozpoczęcie dnia od najistotniejszych spraw. Istniejące filtry Gmaila porządkują wiadomości, lecz nie tworzą kontekstu ani listy działań.

## Rozwiązanie

Usługa łączy Gmail API, zewnętrzny model AI i MCP. Jej kluczowe możliwości to:

- pobiera tylko nowe wiadomości spełniające filtry użytkownika;
- przygotowuje zwięzłe, ustrukturyzowane wyniki: streszczenie, priorytet i działania;
- tworzy raz dziennie rano zapisany digest;
- udostępnia digesty i podsumowania przez narzędzia MCP do zapytań ad hoc;
- ręczne przełączenie analizy między OpenAI API a Anthropic Claude API.

## Zakres MVP

- Lokalne uruchomienie na komputerze użytkownika, lokalny redirect OAuth i harmonogram cron.
- Dostęp do Gmaila tylko do odczytu (`gmail.readonly`).
- Konfigurowalne filtry po nadawcy, etykiecie i słowach kluczowych; domyślnie Inbox z wyłączeniem Promotions i Social.
- Digest raz dziennie rano, zapisany lokalnie i odczytywany przez MCP.
- Narzędzia MCP do pobierania digestu i podsumowań ad hoc.
- OpenAI jako domyślny dostawca oraz Claude API jako ręczna alternatywa.
- Lokalne przechowywanie wyłącznie identyfikatorów Gmaila, hashy, metadanych i podsumowań.
- Wiele lokalnych profili kont, z jednym aktywnym kontem naraz i odseparowanymi filtrami oraz wynikami.

## Poza zakresem MVP

- Publiczna usługa wieloużytkownikowa, współdzielone konta lub równoległe przetwarzanie wielu kont.
- Wysyłanie digestów e-mailem.
- Zapisywanie pełnej treści lub załączników wiadomości.
- Automatyczne wysyłanie odpowiedzi, oznaczanie, archiwizacja lub inne modyfikowanie wiadomości.
- Automatyczne wydobywanie terminów i generowanie proponowanych odpowiedzi.
- Automatyczne przełączanie dostawcy AI oraz analiza każdego maila przez oba modele.

## Zasady kosztu i prywatności

System ogranicza wejście do istotnej treści i zwraca krótki wynik strukturalny. Tokeny OAuth oraz wyniki pozostają lokalne; pełne treści maili nie są utrwalane ani logowane. Użytkownik świadomie wybiera dostawcę AI i konfiguruje jego klucz API.

## Kierunek rozwoju

Po potwierdzeniu jakości digestu usługa może zostać wdrożona na małym serwerze i rozszerzona o kolejne funkcje. Każde rozszerzenie dostępu do Gmaila wymaga osobnej oceny OAuth, prywatności i bezpieczeństwa.
