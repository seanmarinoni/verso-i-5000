"""Verso i 5.000 — l'interfaccia.

Tre pagine: Dashboard, Nuova operazione, Storico. Qui non si calcola niente:
i conti stanno in calcoli.py, la lettura e la scrittura in storage.py.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from html import escape

import pandas as pd
import streamlit as st

import calcoli as c
import grafici as g
import storage

st.set_page_config(page_title="Verso i 5.000", page_icon="🎯", layout="centered")

PAGINE = ["Dashboard", "Nuova operazione", "Storico"]

NOME_TIPO = {
    c.ACQUISTO: "Compro",
    c.VENDITA: "Vendo",
    c.VERSAMENTO: "Verso capitale",
}

STILE = f"""
<style>
  /* Pulsanti grandi: l'app si usa col pollice. */
  .stButton > button, .stFormSubmitButton > button {{
      width: 100%;
      padding: 0.6rem 0.8rem;
      border-radius: 14px;
      font-size: 1.02rem;
      font-weight: 600;
  }}
  div[data-testid="stTextInput"] input, div[data-testid="stDateInput"] input {{
      font-size: 1.1rem;
      padding: 0.6rem 0.7rem;
  }}
  .titolo {{
      font-size: 1.6rem;
      font-weight: 700;
      color: {c.COLORI["blu"]};
      margin-bottom: 0;
  }}
  .sottotitolo {{
      color: {c.COLORI["arancione"]};
      font-weight: 600;
      margin-top: 0;
  }}
  .riepilogo {{
      background: rgba(255, 255, 255, 0.75);
      border-left: 6px solid {c.COLORI["arancione"]};
      border-radius: 14px;
      padding: 0.7rem 1rem;
      margin: 0.6rem 0 1rem 0;
  }}
  .riepilogo .voce {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.18rem 0;
  }}
  .riepilogo .etichetta {{ color: #5F5F5F; }}
  .riepilogo .valore {{ font-weight: 700; text-align: right; }}
  .tessera {{
      background: rgba(255, 255, 255, 0.75);
      border-radius: 16px;
      padding: 0.9rem 0.5rem;
      text-align: center;
      margin-bottom: 0.7rem;
  }}
  .tessera .valore {{
      font-size: 1.55rem;
      font-weight: 700;
      line-height: 1.15;
      color: {c.COLORI["testo"]};
  }}
  .tessera .etichetta {{
      font-size: 0.78rem;
      color: #5F5F5F;
      margin-top: 0.2rem;
  }}
  .tessera--piccola {{ padding: 0.55rem 0.4rem; }}
  .tessera--piccola .valore {{ font-size: 1.05rem; }}
  .meta {{ margin: 0.3rem 0 1.1rem 0; }}
  .meta .intestazione {{
      display: flex;
      justify-content: space-between;
      font-size: 0.82rem;
      color: #5F5F5F;
      margin-bottom: 0.35rem;
  }}
  .meta .traccia {{
      background: rgba(242, 138, 30, 0.16);
      border-radius: 999px;
      height: 14px;
      overflow: hidden;
  }}
  .meta .riempimento {{
      background: {c.COLORI["arancione"]};
      height: 100%;
      border-radius: 999px;
  }}
  /* Compro/Vendo/Verso capitale: colorati solo al passaggio del mouse o
     alla pressione, non a riposo. Il tasto della modalita' attiva e'
     disattivato, quindi non reagisce. */
  .st-key-scegli_acquisto button:hover:not(:disabled),
  .st-key-scegli_acquisto button:active:not(:disabled) {{
      background-color: {c.COLORI["verde"]} !important;
      border-color: {c.COLORI["verde"]} !important;
      color: white !important;
  }}
  .st-key-scegli_vendita button:hover:not(:disabled),
  .st-key-scegli_vendita button:active:not(:disabled) {{
      background-color: {c.COLORI["rosso"]} !important;
      border-color: {c.COLORI["rosso"]} !important;
      color: white !important;
  }}
  .st-key-scegli_versamento button:hover:not(:disabled),
  .st-key-scegli_versamento button:active:not(:disabled) {{
      background-color: {c.COLORI["blu"]} !important;
      border-color: {c.COLORI["blu"]} !important;
      color: white !important;
  }}
</style>
"""


# --- Mattoncini dell'interfaccia -------------------------------------------


def riquadro(voci) -> None:
    """Il riquadro del riepilogo: coppie (etichetta, valore, colore)."""
    pezzi = []
    for voce in voci:
        etichetta, valore = voce[0], voce[1]
        colore = voce[2] if len(voce) > 2 else None
        stile = f' style="color:{colore}"' if colore else ""
        pezzi.append(
            f'<div class="voce"><span class="etichetta">{escape(str(etichetta))}</span>'
            f'<span class="valore"{stile}>{escape(str(valore))}</span></div>'
        )
    st.markdown(f'<div class="riepilogo">{"".join(pezzi)}</div>', unsafe_allow_html=True)


def tessera(colonna, etichetta, valore, colore=None, piccola=False) -> None:
    """Un numero grande con la sua scritta sotto, dentro la colonna data."""
    classe = "tessera tessera--piccola" if piccola else "tessera"
    stile = f' style="color:{colore}"' if colore else ""
    colonna.markdown(
        f'<div class="{classe}"><div class="valore"{stile}>{escape(str(valore))}</div>'
        f'<div class="etichetta">{escape(str(etichetta))}</div></div>',
        unsafe_allow_html=True,
    )


def barra_obiettivo(stato) -> None:
    """La barra "Verso i 5.000": quanta strada e' stata fatta."""
    percento = round(stato.progresso * 100)
    st.markdown(
        f"""
        <div class="meta">
          <div class="intestazione">
            <span>Verso i 5.000</span>
            <span>{escape(c.euro(stato.patrimonio))} di {escape(c.euro(c.OBIETTIVO))} · {percento}%</span>
          </div>
          <div class="traccia"><div class="riempimento" style="width:{min(100, percento)}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def avvisa(testo: str) -> None:
    """Mette da parte un messaggio da mostrare dopo il ricaricamento."""
    st.session_state["conferma"] = testo


def esegui_salvataggio(azione) -> bool:
    """Esegue un salvataggio su storage.py mostrando un errore chiaro se fallisce.

    Senza questo, un problema di collegamento a GitHub (per esempio il
    token senza i permessi giusti) sembrava semplicemente "non funzionare".
    """
    try:
        azione()
    except storage.ErroreArchivio as errore:
        st.error(f"Non sono riuscita a salvare: {errore}")
        return False
    return True


def azzera(chiavi) -> None:
    for chiave in chiavi:
        st.session_state.pop(chiave, None)


def campo_numero(etichetta, chiave, iniziale="", aiuto=None):
    """Un campo per un numero scritto all'italiana: 3,50 oppure 3.50."""
    if chiave not in st.session_state and iniziale != "":
        st.session_state[chiave] = iniziale
    testo = st.text_input(etichetta, key=chiave, help=aiuto)
    valore = c.leggi_numero(testo)
    if (testo or "").strip() and valore is None:
        st.caption("Scrivi solo un numero, per esempio 3,50")
    return valore


def campo_data(chiave, etichetta="Quando"):
    return st.date_input(etichetta, value=date.today(), key=chiave, format="DD/MM/YYYY")


def etichetta_lordo(esito: str) -> str:
    return {c.GAIN: "Gain lordo", c.LOSS: "Loss lordo", c.PARI: "Lordo (pari)"}[esito]


def etichetta_netto(esito: str) -> str:
    return {c.GAIN: "Gain netto", c.LOSS: "Loss netto", c.PARI: "Netto (pari)"}[esito]


# --- Testa e navigazione ---------------------------------------------------


def intestazione() -> None:
    st.markdown('<p class="titolo">Verso i 5.000</p>', unsafe_allow_html=True)
    st.markdown('<p class="sottotitolo">il diario del nostro percorso</p>', unsafe_allow_html=True)


def barra_pagine() -> str:
    attuale = st.session_state.get("pagina", PAGINE[0])
    colonne = st.columns(len(PAGINE))
    for colonna, nome in zip(colonne, PAGINE):
        with colonna:
            if st.button(
                nome,
                key=f"vai_{nome}",
                type="primary" if nome == attuale else "secondary",
                width="stretch",
            ):
                st.session_state["pagina"] = nome
                st.rerun()
    st.write("")
    return attuale


# --- Pagina: Nuova operazione ---------------------------------------------


def selettore_tipo() -> str:
    attuale = st.session_state.get("tipo_nuova", c.ACQUISTO)
    colonne = st.columns(3)
    for colonna, tipo in zip(colonne, (c.ACQUISTO, c.VENDITA, c.VERSAMENTO)):
        with colonna:
            # Quello della modalita' attiva e' disattivato (ci sei gia'):
            # gli altri due restano neutri finche' non li tocchi o ci passi
            # sopra, poi si colorano del loro colore (verde/rosso/blu).
            if st.button(
                NOME_TIPO[tipo],
                key=f"scegli_{tipo}",
                disabled=(tipo == attuale),
                width="stretch",
            ):
                st.session_state["tipo_nuova"] = tipo
                azzera(["prodotto_scelto", "procedi_acquisto", "procedi_vendita", "procedi_versamento"])
                st.rerun()
    return attuale


def scegli_prodotto_acquisto(stato):
    """Il prodotto di un acquisto: un pulsante per le posizioni aperte, o un nome nuovo."""
    scelto = st.session_state.get("prodotto_scelto")
    if not stato.posizioni:
        scelto = "★nuovo"  # niente posizioni aperte: e' per forza un prodotto nuovo

    if scelto == "★nuovo":
        nome = st.text_input(
            "Che prodotto hai comprato",
            key="nome_nuovo",
            help="Scrivilo come vuoi, per esempio come nel messaggio di Sean.",
        )
        if stato.posizioni and st.button("Scegli invece tra le tue posizioni", key="torna_elenco"):
            azzera(["prodotto_scelto"])
            st.rerun()
        return c.nome_pulito(nome)

    if scelto:
        posizione = stato.posizione(scelto)
        if posizione is not None:
            st.markdown(
                f"Altre quote di **{posizione.prodotto}** "
                f"({c.quote_testo(posizione.quote)} quote, PMC {c.euro(posizione.pmc)})"
            )
            if st.button("Cambia prodotto", key="cambia_prodotto"):
                azzera(["prodotto_scelto"])
                st.rerun()
            return posizione.prodotto
        azzera(["prodotto_scelto"])

    st.markdown("**Le tue posizioni aperte**")
    for posizione in stato.posizioni:
        if st.button(
            f"{posizione.prodotto}  ·  {c.quote_testo(posizione.quote)} quote",
            key=f"apri_{posizione.chiave}",
        ):
            st.session_state["prodotto_scelto"] = posizione.prodotto
            st.rerun()
    if st.button("Nuovo prodotto", key="scegli_nuovo"):
        st.session_state["prodotto_scelto"] = "★nuovo"
        st.rerun()
    return None


def scegli_posizione(stato):
    """Il prodotto di una vendita: sempre scelto tra le posizioni aperte."""
    if len(stato.posizioni) == 1:
        return stato.posizioni[0]

    scelto = st.session_state.get("prodotto_scelto")
    posizione = stato.posizione(scelto) if scelto else None
    if posizione is not None:
        st.markdown(
            f"Vendi **{posizione.prodotto}** "
            f"({c.quote_testo(posizione.quote)} quote, PMC {c.euro(posizione.pmc)})"
        )
        if st.button("Cambia prodotto", key="cambia_prodotto_vendita"):
            azzera(["prodotto_scelto"])
            st.rerun()
        return posizione

    st.markdown("**Che prodotto vendi**")
    for aperta in stato.posizioni:
        if st.button(
            f"{aperta.prodotto}  ·  {c.quote_testo(aperta.quote)} quote",
            key=f"vendi_{aperta.chiave}",
        ):
            st.session_state["prodotto_scelto"] = aperta.prodotto
            st.rerun()
    return None


def modulo_acquisto(operazioni, stato) -> None:
    prodotto = scegli_prodotto_acquisto(stato)

    with st.form("form_acquisto"):
        quote = campo_numero("Quante quote", "quote_acquisto")
        prezzo = campo_numero("Prezzo di ogni quota", "prezzo_acquisto")
        giorno = campo_data("data_acquisto")
        if st.form_submit_button("Procedi", type="primary", width="stretch"):
            st.session_state["procedi_acquisto"] = True

    if not st.session_state.get("procedi_acquisto"):
        st.caption("Compila i campi e premi Procedi per vedere il riepilogo.")
        return
    if not prodotto or not quote or not prezzo:
        st.error("Scrivi il prodotto, le quote e il prezzo prima di procedere.")
        return

    nuova = c.Operazione(
        id=c.prossimo_id(operazioni),
        data=giorno,
        tipo=c.ACQUISTO,
        prodotto=prodotto,
        quote=quote,
        prezzo=prezzo,
        commissione=c.COMMISSIONE_DEFAULT,
    )
    errori = c.valida(operazioni, nuova)
    if errori:
        for errore in errori:
            st.error(errore)
        return

    riga, dopo = c.anteprima(operazioni, nuova)
    riquadro(
        [
            ("Spendi", c.euro(riga.costo)),
            ("di cui commissione", c.euro(nuova.commissione), c.COLORI["grigio"]),
            ("Quote dopo l'acquisto", c.quote_testo(riga.quote_dopo)),
            ("Nuovo PMC", c.euro(riga.pmc_dopo), c.COLORI["arancione"]),
            ("Liquidita' dopo", c.euro(dopo.liquidita), c.COLORI["blu"]),
        ]
    )
    if st.button("Salva", key="salva_acquisto", type="primary"):
        if esegui_salvataggio(lambda: storage.salva(nuova)):
            avvisa(
                f"Segnato: {c.quote_testo(quote)} quote di {prodotto} a {c.euro(prezzo)}. "
                f"Ora la posizione e' di {c.quote_testo(riga.quote_dopo)} quote, PMC {c.euro(riga.pmc_dopo)}."
            )
            azzera(
                [
                    "quote_acquisto",
                    "prezzo_acquisto",
                    "data_acquisto",
                    "prodotto_scelto",
                    "nome_nuovo",
                    "procedi_acquisto",
                ]
            )
            st.rerun()


def modulo_vendita(operazioni, stato) -> None:
    if not stato.posizioni:
        st.info("Non hai posizioni aperte: non c'e' niente da vendere.")
        return

    posizione = scegli_posizione(stato)
    if posizione is None:
        return

    with st.form("form_vendita"):
        quote = campo_numero(
            "Quante quote",
            f"quote_vendita_{posizione.chiave}",
            iniziale=c.quote_testo(posizione.quote),
            aiuto="Ci sono gia' tutte le tue quote: abbassale se ne vendi solo una parte.",
        )
        prezzo = campo_numero("Prezzo di ogni quota", "prezzo_vendita")
        giorno = campo_data("data_vendita")
        if st.form_submit_button("Procedi", type="primary", width="stretch"):
            st.session_state["procedi_vendita"] = True

    if not st.session_state.get("procedi_vendita"):
        st.caption("Compila i campi e premi Procedi per vedere il riepilogo.")
        return
    if not quote or not prezzo:
        st.error("Scrivi quote e prezzo prima di procedere.")
        return

    nuova = c.Operazione(
        id=c.prossimo_id(operazioni),
        data=giorno,
        tipo=c.VENDITA,
        prodotto=posizione.prodotto,
        quote=quote,
        prezzo=prezzo,
        commissione=c.COMMISSIONE_DEFAULT,
    )
    errori = c.valida(operazioni, nuova)
    if errori:
        for errore in errori:
            st.error(errore)
        return

    riga, dopo = c.anteprima(operazioni, nuova)
    colore = c.colore_esito(riga.lordo)
    voci = [
        ("Incassi", c.euro(riga.incasso)),
        ("di cui commissione", f"-{c.euro(nuova.commissione)}", c.COLORI["grigio"]),
        (etichetta_lordo(riga.esito_vendita), c.euro(riga.lordo, segno=True), colore),
    ]
    if riga.perdite_usate:
        voci.append(("Perdite compensate", c.euro(riga.perdite_usate), c.COLORI["grigio"]))
    voci.append(("Tasse (26%)", c.euro(riga.tasse), c.COLORI["grigio"]))
    voci.append((etichetta_netto(riga.esito_vendita), c.euro(riga.netto, segno=True), colore))
    if riga.chiude_posizione:
        voci.append(("Dopo la vendita", "posizione chiusa"))
    else:
        voci.append(
            ("Dopo la vendita", f"{c.quote_testo(riga.quote_restanti)} quote, PMC {c.euro(riga.pmc)}")
        )
    voci.append(("Liquidita' dopo", c.euro(dopo.liquidita), c.COLORI["blu"]))
    riquadro(voci)

    if st.button("Salva", key="salva_vendita", type="primary"):
        if esegui_salvataggio(lambda: storage.salva(nuova)):
            avvisa(
                f"Segnato: vendute {c.quote_testo(quote)} quote di {posizione.prodotto} a {c.euro(prezzo)}. "
                f"{etichetta_netto(riga.esito_vendita)} {c.euro(riga.netto, segno=True)}."
            )
            azzera(
                [
                    f"quote_vendita_{posizione.chiave}",
                    "prezzo_vendita",
                    "data_vendita",
                    "prodotto_scelto",
                    "procedi_vendita",
                ]
            )
            st.rerun()


def modulo_versamento(operazioni, stato) -> None:
    with st.form("form_versamento"):
        importo = campo_numero("Quanto hai versato", "importo_versamento")
        giorno = campo_data("data_versamento")
        if st.form_submit_button("Procedi", type="primary", width="stretch"):
            st.session_state["procedi_versamento"] = True

    if not st.session_state.get("procedi_versamento"):
        st.caption("Scrivi l'importo e premi Procedi per vedere il riepilogo.")
        return
    if not importo:
        st.error("Scrivi l'importo prima di procedere.")
        return

    nuova = c.Operazione(
        id=c.prossimo_id(operazioni), data=giorno, tipo=c.VERSAMENTO, prezzo=importo
    )
    errori = c.valida(operazioni, nuova)
    if errori:
        for errore in errori:
            st.error(errore)
        return

    _, dopo = c.anteprima(operazioni, nuova)
    riquadro(
        [
            ("Versi", c.euro(importo)),
            ("Capitale versato dopo", c.euro(dopo.capitale_versato), c.COLORI["azzurro"]),
            ("Liquidita' dopo", c.euro(dopo.liquidita), c.COLORI["blu"]),
            ("Il risultato dei trade", "non cambia", c.COLORI["grigio"]),
        ]
    )
    if st.button("Salva", key="salva_versamento", type="primary"):
        if esegui_salvataggio(lambda: storage.salva(nuova)):
            avvisa(
                f"Segnato il versamento di {c.euro(importo)}. "
                f"Capitale versato: {c.euro(dopo.capitale_versato)}."
            )
            azzera(["importo_versamento", "data_versamento", "procedi_versamento"])
            st.rerun()


def pagina_nuova(operazioni, stato) -> None:
    st.markdown("### Nuova operazione")
    tipo = selettore_tipo()
    st.write("")
    if tipo == c.ACQUISTO:
        modulo_acquisto(operazioni, stato)
    elif tipo == c.VENDITA:
        modulo_vendita(operazioni, stato)
    else:
        modulo_versamento(operazioni, stato)


# --- Pagina: Storico -------------------------------------------------------

COLORE_MARKDOWN = {c.GAIN: "green", c.LOSS: "red", c.PARI: "gray"}


def etichetta_storico(riga) -> str:
    giorno = c.data_testo(riga.data)
    if riga.tipo == c.VERSAMENTO:
        return f"{giorno} · Verso capitale · :blue[{c.euro(riga.importo)}]"
    if riga.tipo == c.ACQUISTO:
        return (
            f"{giorno} · Compro {riga.prodotto} · "
            f"{c.quote_testo(riga.operazione.quote)} quote a {c.euro(riga.operazione.prezzo)}"
        )
    if riga.netto is None:
        return f"{giorno} · Vendo {riga.prodotto} · :red[da correggere]"
    colore = COLORE_MARKDOWN[riga.esito_vendita]
    return (
        f"{giorno} · Vendo {riga.prodotto} · "
        f":{colore}[{c.euro(riga.netto, segno=True)} netto]"
    )


def dettaglio_storico(riga) -> None:
    if riga.errore:
        st.error(riga.errore)
    if riga.tipo == c.VERSAMENTO:
        riquadro([("Capitale versato", c.euro(riga.importo), c.COLORI["azzurro"])])
    elif riga.tipo == c.ACQUISTO:
        riquadro(
            [
                ("Speso", c.euro(riga.costo)),
                ("Quote dopo l'acquisto", c.quote_testo(riga.quote_dopo)),
                ("PMC dopo l'acquisto", c.euro(riga.pmc_dopo), c.COLORI["arancione"]),
            ]
        )
    elif riga.lordo is not None:
        colore = c.colore_esito(riga.lordo)
        voci = [
            ("Incassato", c.euro(riga.incasso)),
            (etichetta_lordo(riga.esito_vendita), c.euro(riga.lordo, segno=True), colore),
        ]
        if riga.perdite_usate:
            voci.append(("Perdite compensate", c.euro(riga.perdite_usate), c.COLORI["grigio"]))
        voci += [
            ("Tasse", c.euro(riga.tasse), c.COLORI["grigio"]),
            (etichetta_netto(riga.esito_vendita), c.euro(riga.netto, segno=True), colore),
            (
                "Dopo la vendita",
                "posizione chiusa"
                if riga.chiude_posizione
                else f"{c.quote_testo(riga.quote_restanti)} quote",
            ),
        ]
        riquadro(voci)
    if riga.operazione.nota:
        st.caption(f"Nota: {riga.operazione.nota}")


def modulo_correzione(operazioni, riga) -> None:
    operazione = riga.operazione
    identificativo = operazione.id

    with st.form(f"correggi_{identificativo}"):
        st.markdown("**Correggi**")
        giorno = st.date_input("Quando", value=operazione.data, format="DD/MM/YYYY")
        tipo = st.selectbox(
            "Cosa",
            options=list(NOME_TIPO),
            index=list(NOME_TIPO).index(operazione.tipo) if operazione.tipo in NOME_TIPO else 0,
            format_func=lambda valore: NOME_TIPO[valore],
        )
        prodotto = st.text_input("Prodotto", value=operazione.prodotto)
        quote = st.text_input("Quote", value=c.quote_testo(operazione.quote))
        prezzo = st.text_input(
            "Prezzo di ogni quota", value=c.numero(operazione.prezzo)
        )
        commissione = st.text_input("Commissione", value=c.numero(operazione.commissione))
        nota = st.text_input("Nota (facoltativa)", value=operazione.nota)
        confermata = st.form_submit_button("Salva la correzione", type="primary")

    if not confermata:
        return

    numeri = {
        "quote": c.leggi_numero(quote) or 0.0,
        "prezzo": c.leggi_numero(prezzo),
        "commissione": c.leggi_numero(commissione) or 0.0,
    }
    if numeri["prezzo"] is None:
        st.error("Il prezzo non si capisce: scrivi solo un numero, per esempio 3,50.")
        return

    corretta = dataclasses.replace(
        operazione,
        data=giorno,
        tipo=tipo,
        prodotto=c.nome_pulito(prodotto),
        quote=numeri["quote"],
        prezzo=numeri["prezzo"],
        commissione=numeri["commissione"],
        nota=nota.strip(),
    )
    altre = [o for o in operazioni if o.id != identificativo]
    # Qui gli avvisi non bloccano: durante una correzione il conto puo' passare
    # per uno stato impossibile (per esempio mentre si sistema l'ordine di due
    # operazioni) e restare bloccati sarebbe peggio.
    problemi = c.valida(altre, corretta, blocca_liquidita=False)
    if esegui_salvataggio(lambda: storage.aggiorna(corretta)):
        messaggio = "Correzione salvata: l'app ha rifatto tutti i conti."
        if problemi:
            messaggio += " Attenzione: " + " ".join(problemi)
        avvisa(messaggio)
        st.rerun()


def modulo_elimina(riga) -> None:
    identificativo = riga.operazione.id
    chiave = f"conferma_elimina_{identificativo}"
    if st.session_state.get(chiave):
        st.warning("Elimino questa operazione? L'app rifara' tutti i conti senza di lei.")
        sinistra, destra = st.columns(2)
        with sinistra:
            if st.button("Si', elimina", key=f"elimina_si_{identificativo}", type="primary"):
                if esegui_salvataggio(lambda: storage.elimina(identificativo)):
                    azzera([chiave])
                    avvisa("Operazione eliminata: l'app ha rifatto tutti i conti.")
                    st.rerun()
        with destra:
            if st.button("Annulla", key=f"elimina_no_{identificativo}"):
                azzera([chiave])
                st.rerun()
    elif st.button("Elimina questa operazione", key=f"elimina_{identificativo}"):
        st.session_state[chiave] = True
        st.rerun()


def pagina_storico(operazioni, stato) -> None:
    st.markdown("### Storico")
    if not stato.righe:
        st.info("Non c'e' ancora nessuna operazione. Segnala dalla pagina Nuova operazione.")
        return

    problemi = [riga for riga in stato.righe if riga.errore]
    if problemi:
        st.warning(
            "Qualcosa non torna:\n"
            + "\n".join(f"- {c.data_testo(riga.data)}: {riga.errore}" for riga in problemi)
        )

    for riga in reversed(stato.righe):
        with st.expander(etichetta_storico(riga)):
            dettaglio_storico(riga)
            modulo_correzione(operazioni, riga)
            modulo_elimina(riga)


# --- Pagina: Dashboard (passo 3) ------------------------------------------


def pagina_dashboard(stato) -> None:
    st.markdown("### Dashboard")

    colore_risultato = c.colore_esito(stato.netto_totale)

    riga1_sinistra, riga1_destra = st.columns(2)
    tessera(riga1_sinistra, "i soldi che hai messo tu", c.euro(stato.capitale_versato), c.COLORI["azzurro"])
    tessera(
        riga1_destra,
        "dopo commissioni e tasse: quello che ti resta",
        c.euro(stato.netto_totale, segno=True),
        colore_risultato,
    )

    riga2_sinistra, riga2_destra = st.columns(2)
    tessera(
        riga2_sinistra,
        "commissioni già tolte, prima delle tasse",
        c.euro(stato.lordo_totale, segno=True),
        c.colore_esito(stato.lordo_totale),
    )
    tessera(riga2_destra, "capitale versato più risultato netto", c.euro(stato.patrimonio), c.COLORI["arancione"])

    tessera(
        st,
        "quanto hai libero per comprare: deve coincidere con Trade Republic",
        c.euro(stato.liquidita),
        c.COLORI["blu"],
    )

    riga3_sinistra, riga3_destra = st.columns(2)
    tessera(
        riga3_sinistra,
        "trattenute sui guadagni",
        c.euro(stato.tasse_totali),
        c.COLORI["grigio"],
        piccola=True,
    )
    tessera(
        riga3_destra,
        "abbassano le tasse sui guadagni futuri",
        c.euro(stato.perdite_da_compensare),
        c.COLORI["grigio"],
        piccola=True,
    )

    barra_obiettivo(stato)

    st.write("")
    mostra_lordo = st.checkbox("Mostra anche il lordo", key="mostra_lordo")
    st.plotly_chart(g.grafico_rendimento(stato, mostra_lordo), width="stretch")
    st.plotly_chart(g.grafico_patrimonio(stato), width="stretch")
    st.plotly_chart(g.grafico_trade_chiusi(stato), width="stretch")

    st.markdown("#### Posizioni aperte")
    if stato.posizioni:
        tabella = pd.DataFrame(
            [
                {
                    "Prodotto": p.prodotto,
                    "Quote": c.quote_testo(p.quote),
                    "PMC": c.euro(p.pmc),
                    "Investito": c.euro(p.investito),
                }
                for p in stato.posizioni
            ]
        )
        st.dataframe(tabella, hide_index=True, width="stretch")
    else:
        st.info("Nessuna posizione aperta al momento.")
    st.plotly_chart(g.grafico_posizioni(stato), width="stretch")

    st.write("")
    immagine = g.immagine_dashboard(stato)
    st.download_button(
        "Salva come immagine",
        data=immagine,
        file_name=f"verso-i-5000-{date.today().isoformat()}.png",
        mime="image/png",
        type="primary",
        width="stretch",
    )


# --- Pagina d'accesso -------------------------------------------------------


def accesso_consentito() -> bool:
    return bool(st.session_state.get("accesso_ok"))


def pagina_accesso() -> None:
    """Foto e password: senza la password giusta non si vede altro."""
    st.markdown(STILE, unsafe_allow_html=True)
    intestazione()

    try:
        foto = storage.leggi_foto()
    except storage.ErroreArchivio as errore:
        foto = None
        st.warning(f"Non riesco a mostrare la foto: {errore}")
    if foto:
        st.image(foto, width="stretch")

    with st.form("accesso"):
        password = st.text_input("Password", type="password")
        entra = st.form_submit_button("Entra", type="primary", width="stretch")

    if not entra:
        return

    password_vera = st.secrets.get("password")
    if not password_vera:
        st.error("Manca la password nei secrets dell'app: controlla .streamlit/secrets.toml.")
    elif password == password_vera:
        st.session_state["accesso_ok"] = True
        st.rerun()
    else:
        st.error("Password sbagliata.")


# --- Avvio ----------------------------------------------------------------


def main() -> None:
    if not accesso_consentito():
        pagina_accesso()
        return

    st.markdown(STILE, unsafe_allow_html=True)
    intestazione()

    try:
        operazioni = storage.leggi()
    except storage.ErroreArchivio as errore:
        st.error(str(errore))
        st.stop()

    stato = c.ricalcola(operazioni)
    pagina = barra_pagine()

    conferma = st.session_state.pop("conferma", None)
    if conferma:
        st.success(conferma)

    if pagina == "Dashboard":
        pagina_dashboard(stato)
    elif pagina == "Nuova operazione":
        pagina_nuova(operazioni, stato)
    else:
        pagina_storico(operazioni, stato)


main()
