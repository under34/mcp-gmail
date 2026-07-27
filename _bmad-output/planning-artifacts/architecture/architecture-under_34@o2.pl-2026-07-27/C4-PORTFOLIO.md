# Usługa MCP dla Gmaila — diagram C4 do portfolio

## Poziom 1: Context

```mermaid
flowchart LR
  U[Właściciel konta Gmail] --> C[Klient MCP]
  U --> G[Google OAuth]
  C --> S[Usługa MCP dla Gmaila]
  S --> G
  S --> GM[Gmail API]
  S --> O[OpenAI API]
  S --> A[Claude API]
  G --> GM
```

Lokalna usługa MCP pobiera wyłącznie dozwolone Wątki Gmaila, tworzy Digesty i Podsumowania Wątków przez OpenAI, a Claude wykorzystuje wyłącznie do ręcznego porównania pojedynczego Wątku. Klient MCP otrzymuje tylko ustrukturyzowane wyniki oraz status kompletności.

## Poziom 2: Container

```mermaid
flowchart TB
  CLIENT[Klient MCP] -->|stdio| SERVER[FastMCP server]
  CRON[Systemowy cron] -->|CLI| BOOT[Bootstrap + use cases]
  SERVER --> BOOT
  BOOT --> GMAIL[GmailAdapter]
  BOOT --> SUMMARY[OpenAIAdapter / ClaudeAdapter]
  BOOT --> REPO[SQLiteAdapter]
  GMAIL --> GAPI[Gmail API]
  SUMMARY --> OAI[OpenAI API]
  SUMMARY --> CLAUDE[Claude API]
  REPO --> DB[(Lokalny SQLite)]
```

Granice demonstratora:

- FastMCP używa lokalnego transportu `stdio`; nie ma publicznego endpointu HTTP.
- Systemowy cron i serwer MCP korzystają z tych samych przypadków użycia.
- SQLite przechowuje metadane, hashe, statusy i podsumowania maksymalnie 30 dni.
- Token OAuth i klucze AI nie są przekazywane klientowi MCP ani zapisywane w repozytorium.
