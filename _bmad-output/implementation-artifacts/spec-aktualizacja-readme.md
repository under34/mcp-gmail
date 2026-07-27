---
title: 'Aktualizacja README projektu Gmail MCP'
type: 'chore'
created: '2026-07-27'
status: 'done'
route: 'one-shot'
---

# Aktualizacja README projektu Gmail MCP

## Intent

**Problem:** README opisywał tylko podstawowe uruchomienie i nie wyjaśniał gotowego
lokalnego OAuth Gmail ani aktualnych granic MVP.

**Approach:** Uzupełnić dokumentację o rzeczywisty zakres, konfigurację Google
OAuth, komendy CLI, zmienne środowiskowe i zasady bezpieczeństwa.

## Suggested Review Order

- README odróżnia gotowy OAuth od funkcji planowanych w dalszych historiach.
  [`README.md:1`](../../README.md#L1)

- Instrukcja prowadzi od konfiguracji Google Cloud do bezpiecznego połączenia konta.
  [`README.md:43`](../../README.md#L43)

- Opis poleceń i ochrony danych odpowiada zachowaniu aktualnego CLI.
  [`README.md:65`](../../README.md#L65)
