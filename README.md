# Verso i 5.000

Il diario del percorso di trading: ogni acquisto, vendita o versamento si
segna in pochi secondi, e l'app calcola da sola PMC, tasse (26% con
compensazione delle minusvalenze) e commissioni.

La specifica completa è nel manuale del progetto (non incluso in questo
repository pubblico).

## Struttura

- `app.py` — interfaccia Streamlit: Dashboard, Nuova operazione, Storico.
- `calcoli.py` — tutta la logica (PMC, lordo, tasse, perdite da compensare,
  liquidità, patrimonio). Funzioni pure, senza Streamlit.
- `storage.py` — lettura e scrittura delle operazioni e della foto di
  accesso, su un repository GitHub privato separato.
- `grafici.py` — grafici Plotly e il PNG completo (matplotlib) per "Salva
  come immagine".
- `tests/` — test automatici di `calcoli.py` (pytest).

## Dati e segreti

Questo repository contiene solo il codice. Le operazioni, la foto e la
password non ci sono mai: vivono nei secrets di Streamlit e in un secondo
repository GitHub privato.

## Provare in locale

```
pip install -r requirements.txt
python -m streamlit run app.py
```

Serve un file `.streamlit/secrets.toml` (non incluso, è nel `.gitignore`)
con `password`, `github_token` e `github_repo_dati`.
