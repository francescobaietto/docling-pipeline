# docling-pipeline

Converte PDF in Markdown e tabelle strutturate con [Docling](https://github.com/docling-project/docling)
e li consegna a un workflow n8n, che si occupa di estrazione con LLM e di salvare tutto su
Google Sheets. Questo repository contiene il software della conversione, i suoi test e il
modo in cui viene eseguito.

## Come funziona

```
n8n  <──ping/pending/result/status──  docling_pipeline (container)
```
1. sveglia n8n (`/ping`, con tentativi) e chiede i documenti da elaborare (`/pending`);
2. per ogni PDF: scarica (solo https, limite di dimensione, controllo `%PDF`), converte con
   Docling, esegue controlli strutturali sulle tabelle;
3. consegna Markdown + metadati e poi una chiamata per tabella (`/result`);
4. attende (`/status`) che n8n finisca; esce con codice ≠ 0 se qualcosa è fallito.

Il contratto completo è in [`docs/n8n-contract.md`](docs/n8n-contract.md).

## Struttura

| Percorso | Contenuto |
|---|---|
| `docling_pipeline/` | codice: `runner`, `n8n_client`, `converter`, `checks`, `config` |
| `tests/` | test unitari (veloci, senza Docling) e un test di integrazione con Docling |
| `Dockerfile` | immagine runtime con Docling CPU-only e modelli già scaricati |
| `.github/workflows/ci.yml` | test a ogni push e pull request |
| `.github/workflows/image.yml` | costruisce e pubblica l'immagine su GHCR quando il codice cambia |
| `.github/workflows/e2e.yml` | validazione end-to-end quotidiana sui documenti forniti da n8n |

## Configurazione

Secrets del repository (Settings → Secrets and variables → Actions):
- `N8N_BASE_URL`: URL base dei webhook di n8n
- `N8N_TOKEN`: token condiviso con n8n

Variabili opzionali (con default): `WAKE_TIMEOUT_S=300`, `WAKE_INTERVAL_S=10`,
`STATUS_TIMEOUT_S=2400`, `STATUS_INTERVAL_S=60`, `MAX_PDF_MB=50`, `MAX_DOCS_PER_RUN=10`,
`DO_OCR=false`.

## Test

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -t . -v          # unitari, pochi secondi
RUN_DOCLING_TESTS=1 python -m unittest tests.test_docling_integration   # richiede Docling
python -m tests.make_fixture                          # rigenera il PDF sintetico di test
```

## Politica sui log
Il repository è pubblico e i log delle esecuzioni sono visibili: la pipeline registra solo
id, conteggi e durate, mai contenuti dei documenti. Non aggiungere log di Markdown, tabelle
o URL.

## Portabilità
Il runner dipende solo da variabili d'ambiente e parla con n8n via HTTP: la stessa immagine
può girare altrove (per esempio come job su un altro provider) senza modifiche al codice né ai
workflow n8n.
