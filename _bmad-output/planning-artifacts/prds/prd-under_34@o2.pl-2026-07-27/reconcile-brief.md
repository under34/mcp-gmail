# Uzgodnienie briefu i PRD

Poniżej są wyłącznie rozbieżności mające wpływ na zakres lub implementowalne wymagania.

1. **Claude poza rolą „alternatywy porównawczej”.** Brief określa Claude API jako ręcznie wybieraną *alternatywę porównawczą* i wyłącza analizowanie każdego maila przez oba modele. PRD rozszerza to na `summarize_gmail`, gdzie Claude może analizować dowolny Filtr Gmail (FR-7, FR-9), a nie tylko wskazany Wątek w `compare_summaries`. Należy potwierdzić, czy Claude ma być dostępny dla dowolnego podsumowania ad hoc, czy wyłącznie dla jawnego porównania pojedynczego Wątku.

2. **Możliwe obejście skonfigurowanego Filtru Gmail przez porównanie.** Brief obiecuje pobieranie tylko wiadomości zgodnych z filtrami użytkownika. PRD wymaga dla `compare_summaries` jedynie jednoznacznego identyfikatora Wątku i potwierdzenia (FR-8); nie stanowi, że ten Wątek musi pasować do aktywnego Filtru Gmail ani że użytkownik widzi rozszerzenie zakresu. To umożliwia analizę treści spoza konfigurowanego zakresu. Trzeba dodać ograniczenie do Filtru albo jawny, osobny mechanizm rozszerzenia zakresu.

3. **Niedookreślony wybór dostawcy dla automatycznego Digestu.** Brief wymaga porannego Digestu uruchamianego z crona, natomiast PRD wymaga jawnego wyboru Dostawcy AI dla operacji i pokazania go przed wysłaniem treści (FR-9/FR-10). Nie określa, czy Harmonogram używa zapisanego dostawcy (np. domyślnego OpenAI), kiedy użytkownik go wybiera ani co dzieje się po zmianie konfiguracji. Bez tego automatyczny przebieg nie ma jednoznacznej, zgodnej z kontrolą użytkownika reguły wyboru dostawcy.
