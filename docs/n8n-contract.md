# Contratto tra pipeline e n8n

La pipeline è il lato **attivo**: sveglia n8n, chiede cosa fare, consegna i risultati e
aspetta che n8n abbia finito. n8n espone quattro webhook e non sa dove gira la pipeline
(GitHub Actions oggi, un altro host domani).

Base URL: `N8N_BASE_URL` (es. `https://<servizio>.onrender.com/webhook`).
Ogni richiesta porta l'header `X-Pipeline-Token: <N8N_TOKEN>`; n8n risponde 401 se non coincide.

## `GET /ping`
Risponde `200` con `{"status": "ok"}`. Serve solo a svegliare e verificare n8n.
La pipeline riprova ogni 10 s fino a 5 minuti (cold start di Render free).

## `GET /pending?limit=N`
Documenti da elaborare, al massimo `N`.
```json
{"documents": [{"id": "abc123", "url": "https://example.com/report.pdf"}]}
```
- `id`: identificativo stabile scelto da n8n (stesso id = stesso documento).
- `url`: https assoluto, PDF pubblico. Altri schemi vengono rifiutati.
- n8n deve restituire solo documenti con stato `da fare` o `errore` (da ritentare).

## `POST /result`
Corpo JSON, sempre con `run_id` e `document_id`. Tre tipi (`kind`):

**`document`** — inviato per primo, una volta per documento:
```json
{
  "kind": "document", "run_id": "…", "document_id": "abc123",
  "markdown": "# …", "tables_expected": 12,
  "metadata": {"pages": 69, "markdown_chars": 123456, "tables": 12,
               "tables_flagged": 1, "ok": true, "pdf_bytes": 2000000,
               "docling_version": "…", "duration_s": 310.2}
}
```
**`table`** — una chiamata per tabella, dopo il `document`:
```json
{
  "kind": "table", "run_id": "…", "document_id": "abc123",
  "table": {"index": 0, "page": 4, "caption": "", "columns": ["Item", "2026"],
            "rows": [["Revenue", "109,896"]]},
  "check": {"rows": 1, "columns": 2, "numeric_ratio": 1.0, "issues": [], "ok": true}
}
```
**`error`** — se il documento non è convertibile:
```json
{"kind": "error", "run_id": "…", "document_id": "abc123", "error": "ValueError: …"}
```
n8n risponde subito `200` (o `4xx` se il corpo è invalido; la pipeline non ritenta i 4xx,
ritenta i 5xx fino a 3 volte). Il lavoro lento (LLM, scrittura su Sheets) va fatto
**dopo** aver risposto, non dentro la richiesta.

Idempotenza: `(document_id, kind, table.index)` identifica ogni consegna. Se arriva due
volte (un ritentativo), n8n deve sovrascrivere e non duplicare.

## `GET /status?run_id=…`
```json
{"done": false, "pending": 3, "failed": 0}
```
`done` diventa `true` quando n8n ha completato estrazione LLM e scrittura su Sheets di
**tutti** i documenti consegnati in quel `run_id`. `failed` = documenti con errori lato n8n.
La pipeline interroga questo endpoint ogni 60 s (fino a 40 minuti): oltre a sincronizzare
la fine del job, tiene sveglio n8n (Render free dorme dopo 15 minuti senza richieste in ingresso).

## Stato dei documenti
Vive fuori da n8n (foglio Google o Postgres esterno), perché il disco di Render free è
effimero: `da fare → in corso → fatto | errore`.
