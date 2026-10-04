"""Lettura e scrittura delle operazioni, e lettura della foto di accesso.

Tutto vive in un repository GitHub PRIVATO, separato da quello dell'app:
`operazioni.csv` e `foto.png`. L'app parla con GitHub tramite la sua API
REST, con un token letto da `st.secrets` (github_token, github_repo_dati,
e facoltativo github_branch). Ogni salvataggio e' un commit con un
messaggio leggibile, cosi' la cronologia di GitHub e' anche la copia di
sicurezza dei dati.

Il resto dell'app usa solo le funzioni qui sotto: leggi, salva, aggiorna,
elimina, leggi_foto.
"""

from __future__ import annotations

import base64
import csv
import dataclasses
import io

import requests
import streamlit as st

import calcoli as c
from calcoli import Operazione, ordina, prossimo_id

API = "https://api.github.com"
COLONNE = ["id", "data", "tipo", "prodotto", "quote", "prezzo", "commissione", "nota"]
PERCORSO_OPERAZIONI = "operazioni.csv"
PERCORSO_FOTO = "foto.png"
_TIMEOUT = 15

_VERBI = {c.ACQUISTO: "Acquisto", c.VENDITA: "Vendita", c.VERSAMENTO: "Versamento"}


class ErroreArchivio(Exception):
    """Qualcosa non va leggendo o scrivendo i dati su GitHub."""


# --- La configurazione e le chiamate all'API --------------------------------


def _config():
    token = st.secrets.get("github_token")
    repo = st.secrets.get("github_repo_dati")
    if not token or not repo:
        raise ErroreArchivio(
            "Mancano 'github_token' o 'github_repo_dati' nei secrets dell'app."
        )
    branch = st.secrets.get("github_branch", "main")
    return token, repo, branch


def _intestazioni(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _scarica_blob(repo: str, token: str, sha: str) -> bytes:
    """Il contenuto di un file tramite l'API dei blob di git.

    Serve per i file sopra 1 MB (per esempio la foto): l'API "contents" li
    restituisce senza il contenuto, solo con i metadati.
    """
    url = f"{API}/repos/{repo}/git/blobs/{sha}"
    try:
        risposta = requests.get(url, headers=_intestazioni(token), timeout=_TIMEOUT)
    except requests.RequestException as errore:
        raise ErroreArchivio(f"Non riesco a collegarmi a GitHub: {errore}") from errore
    if risposta.status_code != 200:
        raise ErroreArchivio(f"GitHub ha risposto {risposta.status_code} leggendo un file grande.")
    return base64.b64decode(risposta.json()["content"])


def _scarica_bytes(percorso: str):
    """(contenuto in bytes, sha) del file nel repository dati.

    (None, None) se il file non esiste ancora (per esempio la primissima
    volta, prima di qualunque operazione).
    """
    token, repo, branch = _config()
    url = f"{API}/repos/{repo}/contents/{percorso}"
    try:
        risposta = requests.get(
            url, headers=_intestazioni(token), params={"ref": branch}, timeout=_TIMEOUT
        )
    except requests.RequestException as errore:
        raise ErroreArchivio(f"Non riesco a collegarmi a GitHub: {errore}") from errore
    if risposta.status_code == 404:
        return None, None
    if risposta.status_code != 200:
        raise ErroreArchivio(
            f"GitHub ha risposto {risposta.status_code} leggendo {percorso}."
        )
    dati = risposta.json()
    if dati.get("encoding") == "base64" and dati.get("content"):
        return base64.b64decode(dati["content"]), dati["sha"]
    # File sopra 1 MB: "contents" non manda il contenuto, solo i metadati.
    return _scarica_blob(repo, token, dati["sha"]), dati["sha"]


def _scarica_testo(percorso: str):
    contenuto, sha = _scarica_bytes(percorso)
    if contenuto is None:
        return None, None
    return contenuto.decode("utf-8"), sha


def _carica_bytes(percorso: str, contenuto: bytes, messaggio: str, sha: str | None) -> None:
    token, repo, branch = _config()
    url = f"{API}/repos/{repo}/contents/{percorso}"
    corpo = {
        "message": messaggio,
        "content": base64.b64encode(contenuto).decode("ascii"),
        "branch": branch,
    }
    if sha:
        corpo["sha"] = sha
    try:
        risposta = requests.put(url, headers=_intestazioni(token), json=corpo, timeout=_TIMEOUT)
    except requests.RequestException as errore:
        raise ErroreArchivio(f"Non riesco a salvare su GitHub: {errore}") from errore
    if risposta.status_code not in (200, 201):
        raise ErroreArchivio(
            f"GitHub ha rifiutato il salvataggio di {percorso} ({risposta.status_code})."
        )


# --- Le operazioni: lettura, scrittura, messaggi di commit -----------------


def _numero(valore: float) -> str:
    """Numero per il CSV: punto decimale e niente zeri inutili."""
    testo = f"{float(valore):.6f}".rstrip("0").rstrip(".")
    return testo or "0"


def leggi() -> list:
    """Tutte le operazioni salvate, in ordine di data."""
    testo, _ = _scarica_testo(PERCORSO_OPERAZIONI)
    if not testo:
        return []
    operazioni = []
    for numero_riga, dati in enumerate(csv.DictReader(io.StringIO(testo)), start=2):
        if not (dati.get("id") or "").strip():
            continue
        try:
            operazioni.append(Operazione.da_dict(dati))
        except (KeyError, TypeError, ValueError) as errore:
            raise ErroreArchivio(
                f"Riga {numero_riga} di {PERCORSO_OPERAZIONI} illeggibile: {errore}"
            ) from errore
    return ordina(operazioni)


def _testo_csv(operazioni) -> str:
    buffer = io.StringIO()
    scrittore = csv.DictWriter(buffer, fieldnames=COLONNE, lineterminator="\n")
    scrittore.writeheader()
    for operazione in ordina(operazioni):
        scrittore.writerow(
            {
                "id": operazione.id,
                "data": operazione.data.isoformat(),
                "tipo": operazione.tipo,
                "prodotto": operazione.prodotto,
                "quote": _numero(operazione.quote),
                "prezzo": _numero(operazione.prezzo),
                "commissione": _numero(operazione.commissione),
                "nota": operazione.nota,
            }
        )
    return buffer.getvalue()


def _descrizione(operazione: Operazione) -> str:
    """Il cuore del messaggio di commit, per esempio "Acquisto Coinbase 5x long, 4 quote"."""
    if operazione.tipo == c.VERSAMENTO:
        importo = f"{operazione.prezzo:.2f}".replace(".", ",")
        return f"Versamento di {importo} €"
    verbo = _VERBI.get(operazione.tipo, operazione.tipo.capitalize())
    return f"{verbo} {operazione.prodotto}, {c.quote_testo(operazione.quote)} quote"


def _scrivi(operazioni, messaggio: str) -> None:
    _, sha = _scarica_bytes(PERCORSO_OPERAZIONI)
    _carica_bytes(PERCORSO_OPERAZIONI, _testo_csv(operazioni).encode("utf-8"), messaggio, sha)


def salva(nuova: Operazione) -> Operazione:
    """Aggiunge un'operazione. Se non ha un id, le da' il primo libero."""
    operazioni = leggi()
    if not nuova.id:
        nuova = dataclasses.replace(nuova, id=prossimo_id(operazioni))
    elif any(o.id == nuova.id for o in operazioni):
        raise ErroreArchivio(f"Esiste gia' un'operazione con l'id {nuova.id}.")
    _scrivi(operazioni + [nuova], _descrizione(nuova))
    return nuova


def aggiorna(corretta: Operazione) -> None:
    """Sostituisce un'operazione esistente, tenendo lo stesso id."""
    operazioni = leggi()
    if not any(o.id == corretta.id for o in operazioni):
        raise ErroreArchivio(f"Nessuna operazione con l'id {corretta.id} da correggere.")
    _scrivi(
        [corretta if o.id == corretta.id else o for o in operazioni],
        f"Correzione: {_descrizione(corretta)}",
    )


def elimina(id_operazione: int) -> None:
    """Cancella un'operazione."""
    operazioni = leggi()
    eliminata = next((o for o in operazioni if o.id == id_operazione), None)
    if eliminata is None:
        raise ErroreArchivio(f"Nessuna operazione con l'id {id_operazione} da eliminare.")
    restanti = [o for o in operazioni if o.id != id_operazione]
    _scrivi(restanti, f"Eliminazione: {_descrizione(eliminata)}")


def leggi_foto() -> bytes | None:
    """La foto della pagina d'accesso. None se non c'e' ancora."""
    contenuto, _ = _scarica_bytes(PERCORSO_FOTO)
    return contenuto
