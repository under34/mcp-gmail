# Uzgodnienie PRD ↔ Architecture Spine

Zakres: finalny PRD z 2026-07-27 vs. `ARCHITECTURE-SPINE.md` (draft).

1. **Kontrakt priorytetu jest sprzeczny.** PRD FR-4 wymaga wartości `wysoki`, `średni`, `niski`, natomiast AD-6 ustanawia `high`, `medium`, `low` jako walidowany `ThreadSummary`. Trzeba wybrać kanoniczny enum (albo jawnie zdefiniować mapowanie warstwy prezentacji), inaczej wynik MCP nie spełni testowalnego kontraktu PRD.

2. **Brakuje protokołu jawnego potwierdzenia przed przekazaniem treści.** FR-7 i FR-8/FR-9 nakazują pokazać rozwiązany zakres/dostawcę i uzyskać potwierdzenie *przed* pobraniem pełnych treści lub wysłaniem ich do obu dostawców. AD-5/AD-6 jedynie stwierdzają „previewed and confirmed” / „explicitly confirmed”, bez modelu dwufazowego wywołania, tokenu zatwierdzenia, jego zakresu i wygasania. Przy stdio FastMCP samo to nie gwarantuje kontroli danych.

3. **Cykl życia konfiguracji i danych użytkownika nie ma właściciela architektonicznego.** FR-1 i FR-2 wymagają lokalnego odłączenia z usunięciem tokenów oraz podglądu tekstu i liczby dopasowanych wątków przed zapisaniem filtru; FR-5 wymaga włączania/wyłączania oraz zmiany godziny harmonogramu. Spine określa miejsca przechowywania i cron, ale nie definiuje use case’ów/portów ani trwałego modelu tych operacji (w tym walidacji nieobsługiwanego filtru). To grozi implementacją tych wymagań poza `application/` i naruszeniem AD-1/AD-3.

4. **Brakuje mechanizmu zapewnienia jakości wymaganego przez SM-2.** PRD wymaga, aby na ręcznie oznaczonych co najmniej 10 wątkach nie pominąć żadnego `wysoki` i osiągnąć >=80% zgodności priorytetów. Spine ma testy z fiksturami, lecz nie przewiduje zestawu referencyjnego, sposobu oceny ani bramki/raportu jakości; nie da się więc powtarzalnie wykazać metryki sukcesu.

5. **Kontrakt digestu pomija wymagane informacje audytowalne.** FR-3 wymaga dla każdej pozycji linku/ID do źródłowego Gmailowego wątku oraz powodu uwzględnienia. AD-6 ogranicza `ThreadSummary` do streszczenia, priorytetu, działań, dostawcy i statusu, a AD-7 do metadanych całego uruchomienia. Należy rozszerzyć kontrakt pozycji digestu (lub osobny `DigestItem`) o `thread_id`/bezpieczny link i `inclusion_reason`.
