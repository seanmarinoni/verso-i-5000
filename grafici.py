"""I grafici Plotly e l'immagine PNG completa (matplotlib, passo 5).

Qui non si calcola niente: i numeri arrivano gia' pronti da calcoli.py. Ogni
grafico Plotly ha di suo il pulsante per salvarsi come immagine (l'icona della
macchina fotografica nella barra degli strumenti), quindi non serve altro
codice per quello.
"""

from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")  # il PNG si genera sul server, senza finestre grafiche

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from matplotlib.patches import FancyBboxPatch

import calcoli as c

# I colori tenui della torta: versioni chiare di blu, arancione e dei loro
# toni vicini, come chiede il manuale. La liquidita' ha il suo colore fisso,
# per distinguerla sempre dai prodotti.
PALETTE_TORTA = [
    "#A9CDE6",  # blu chiaro
    "#F6C690",  # arancione chiaro
    "#8FC7C2",  # teal, vicino al blu
    "#E9D08A",  # ambra, vicino all'arancione
    "#9FA9D6",  # indaco, vicino al blu dall'altra parte
    "#D9A77E",  # terracotta, vicino all'arancione dall'altra parte
]
LIQUIDITA_COLORE = "#C7CDD1"

_GRIGIO_RECESSIVO = "#D8CDBB"


def _hex_a_rgba01(hex_colore: str, alpha: float):
    """Per matplotlib: (r, g, b, a) da 0 a 1."""
    hex_colore = hex_colore.lstrip("#")
    r, g, b = (int(hex_colore[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b, alpha)


_LAYOUT_BASE = dict(
    plot_bgcolor="white",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="sans-serif", color=c.COLORI["testo"]),
    margin=dict(l=10, r=10, t=30, b=10),
    hoverlabel=dict(bgcolor="white"),
)


def _layout_base(**extra) -> dict:
    layout = dict(_LAYOUT_BASE)
    layout.update(extra)
    return layout


def _assi_recessivi(fig: go.Figure) -> None:
    """Gli assi e le griglie restano sullo sfondo: sottili e discreti."""
    fig.update_xaxes(showgrid=False, linecolor=_GRIGIO_RECESSIVO, tickfont=dict(color="#8A8A8A"))
    fig.update_yaxes(
        showgrid=True,
        gridcolor=_GRIGIO_RECESSIVO,
        gridwidth=1,
        zeroline=False,
        tickfont=dict(color="#8A8A8A"),
    )


def _punti_indice(serie):
    """Un indice per operazione al posto della data vera sull'asse.

    Con la data vera, piu' operazioni nello stesso giorno finiscono tutte
    nello stesso punto e il grafico si schiaccia. Con un indice, ogni
    operazione ha il suo gradino visibile; le date restano comunque nelle
    etichette dell'asse.
    """
    xs = list(range(len(serie)))
    etichette = [c.data_testo(p.data) for p in serie]
    return xs, etichette


def _tacche_diradate(xs, etichette, massimo=7):
    """Al massimo 'massimo' tacche sull'asse, a passi regolari."""
    n = len(xs)
    if n <= massimo:
        return xs, etichette
    passo = max(1, -(-n // massimo))
    indici = list(range(0, n, passo))
    if indici[-1] != n - 1:
        indici.append(n - 1)
    return [xs[i] for i in indici], [etichette[i] for i in indici]


def grafico_andamento(stato: c.Stato) -> go.Figure:
    """Patrimonio e capitale versato in un'unica linea cumulata, un punto per operazione.

    Un segmento per trade, in ordine di operazione e non di data vera (due
    operazioni lo stesso giorno restano comunque due punti distinti): e' il
    diario del portafoglio, non uno scatter sparso nel tempo. Parte dal primo
    versamento, non da uno zero finto prima di qualunque operazione.
    """
    serie = stato.serie[1:] if len(stato.serie) > 1 else stato.serie
    xs, etichette = _punti_indice(serie)
    capitale = [p.capitale for p in serie]
    patrimonio = [p.patrimonio for p in serie]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=capitale,
            mode="lines",
            name="Capitale versato",
            line=dict(color=c.COLORI["azzurro"], width=2),
            hovertemplate="Capitale versato: %{y:,.2f} €<extra></extra>",
        )
    )

    indici_versamento = [
        i for i in range(len(capitale)) if capitale[i] > (capitale[i - 1] if i > 0 else 0)
    ]
    if indici_versamento:
        fig.add_trace(
            go.Scatter(
                x=[xs[i] for i in indici_versamento],
                y=[capitale[i] for i in indici_versamento],
                mode="markers",
                name="Versamento",
                marker=dict(color=c.COLORI["blu"], size=9, line=dict(color="white", width=1.5)),
                hovertemplate="Versamento, capitale: %{y:,.2f} €<extra></extra>",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=patrimonio,
            mode="lines",
            name="Patrimonio",
            line=dict(color=c.COLORI["arancione"], width=3),
            hovertemplate="Patrimonio: %{y:,.2f} €<extra></extra>",
        )
    )

    if serie:
        ultimo = serie[-1]
        scarto = ultimo.patrimonio - ultimo.capitale
        percento = 100 * scarto / ultimo.capitale if ultimo.capitale else 0.0
        # L'ultimo punto e' sempre il piu' a destra: l'etichetta va verso
        # sinistra, altrimenti uscirebbe dal grafico.
        fig.add_annotation(
            x=xs[-1],
            y=ultimo.patrimonio,
            text=f"{c.euro(ultimo.patrimonio)} ({percento:+.1f}%)",
            showarrow=False,
            xanchor="right",
            yanchor="bottom" if scarto >= 0 else "top",
            font=dict(color=c.colore_esito(scarto), size=13),
        )

    fig.update_layout(**_layout_base(title="Andamento del portafoglio", showlegend=True))
    _assi_recessivi(fig)
    if xs:
        tacche_x, tacche_testo = _tacche_diradate(xs, etichette)
        fig.update_xaxes(tickmode="array", tickvals=tacche_x, ticktext=tacche_testo)
    return fig


def grafico_trade_chiusi(stato: c.Stato) -> go.Figure:
    """Una barra per ogni posizione chiusa: l'altezza e' il netto."""
    trades = stato.trade_chiusi
    fig = go.Figure()
    if not trades:
        fig.update_layout(**_layout_base(title="Trade chiusi"))
        _assi_recessivi(fig)
        return fig

    posizioni = list(range(len(trades)))
    colori = [c.colore_esito(t.netto) for t in trades]
    fig.add_trace(
        go.Bar(
            x=posizioni,
            y=[t.netto for t in trades],
            marker_color=colori,
            text=[t.prodotto for t in trades],
            hovertemplate=(
                "%{text}<br>Chiuso il %{customdata}<br>Netto: %{y:,.2f} €<extra></extra>"
            ),
            customdata=[c.data_testo(t.data_chiusura) for t in trades],
            showlegend=False,
        )
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=posizioni,
        ticktext=[c.data_testo(t.data_chiusura) for t in trades],
    )
    fig.update_layout(**_layout_base(title="Trade chiusi"))
    _assi_recessivi(fig)
    return fig


def grafico_posizioni(stato: c.Stato) -> go.Figure:
    """La torta delle posizioni aperte, liquidita' compresa.

    Le fette sono calcolate su quanto e' stato pagato (quote x PMC), non sul
    valore di oggi: l'app non lo conosce.
    """
    etichette = [p.prodotto for p in stato.posizioni]
    valori = [p.investito for p in stato.posizioni]
    colori = [PALETTE_TORTA[i % len(PALETTE_TORTA)] for i in range(len(stato.posizioni))]

    etichette.append("Liquidità")
    valori.append(max(stato.liquidita, 0.0))
    colori.append(LIQUIDITA_COLORE)

    fig = go.Figure(
        go.Pie(
            labels=etichette,
            values=valori,
            marker=dict(colors=colori, line=dict(color="white", width=2)),
            hovertemplate="%{label}: %{value:,.2f} € (%{percent})<extra></extra>",
            textinfo="label+percent",
            textfont=dict(color=c.COLORI["testo"]),
        )
    )
    fig.update_layout(**_layout_base(title="Posizioni aperte e liquidità", showlegend=False))
    return fig


# --- Il PNG completo (matplotlib) ------------------------------------------
#
# Una sola figura verticale, generata sul server: intestazione, numeri, i tre
# grafici, la torta e la tabella dei trade. L'altezza cresce con il numero di
# operazioni, cosi' non si taglia nulla.

_TESSERE_PRINCIPALI = [
    # (etichetta, lambda stato -> (valore_testo, colore), full_larghezza)
    ("i soldi che hai messo tu", lambda s: (c.euro(s.capitale_versato), c.COLORI["azzurro"]), False),
    (
        "dopo commissioni e tasse: quello che ti resta",
        lambda s: (c.euro(s.netto_totale, segno=True), c.colore_esito(s.netto_totale)),
        False,
    ),
    (
        "commissioni già tolte, prima delle tasse",
        lambda s: (c.euro(s.lordo_totale, segno=True), c.colore_esito(s.lordo_totale)),
        False,
    ),
    ("capitale versato più risultato netto", lambda s: (c.euro(s.patrimonio), c.COLORI["arancione"]), False),
    (
        "quanto hai libero per comprare: deve coincidere con Trade Republic",
        lambda s: (c.euro(s.liquidita), c.COLORI["blu"]),
        True,
    ),
]
_TESSERE_PICCOLE = [
    ("trattenute sui guadagni", lambda s: c.euro(s.tasse_totali)),
    ("abbassano le tasse sui guadagni futuri", lambda s: c.euro(s.perdite_da_compensare)),
]


def _tessera_mpl(ax, riquadro, valore, etichetta, colore, piccola=False) -> None:
    """Un numero grande con la sua scritta sotto, dentro il riquadro dato."""
    x0, y0, x1, y1 = riquadro
    pad = 0.006
    ax.add_patch(
        FancyBboxPatch(
            (x0 + pad, y0 + pad),
            (x1 - x0) - 2 * pad,
            (y1 - y0) - 2 * pad,
            boxstyle="round,pad=0,rounding_size=0.015",
            linewidth=0,
            facecolor="white",
            alpha=0.75,
            transform=ax.transAxes,
        )
    )
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ax.text(
        cx,
        cy + 0.22 * (y1 - y0),
        valore,
        ha="center",
        va="center",
        fontsize=11 if piccola else 14,
        fontweight="bold",
        color=colore,
        transform=ax.transAxes,
    )
    ax.text(
        cx,
        cy - 0.24 * (y1 - y0),
        etichetta,
        ha="center",
        va="center",
        fontsize=7 if piccola else 7.8,
        color="#5F5F5F",
        transform=ax.transAxes,
        wrap=True,
    )


def _disegna_intestazione_mpl(ax, oggi: date) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.0, 0.62, "Verso i 5.000", fontsize=19, fontweight="bold", color=c.COLORI["blu"], va="center")
    ax.text(
        0.0,
        0.14,
        f"Aggiornato al {c.data_testo(oggi)}",
        fontsize=10.5,
        color=c.COLORI["arancione"],
        fontweight="semibold",
        va="center",
    )


def _disegna_numeri_mpl(ax, stato: c.Stato) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    righe_doppie = [t for t in _TESSERE_PRINCIPALI if not t[2]]
    piena = [t for t in _TESSERE_PRINCIPALI if t[2]][0]
    confini_y = [1.0, 0.70, 0.40, 0.28]  # 2 righe doppie + 1 riga piena + le due piccole
    for riga, y_alto in enumerate(confini_y[:2]):
        y_basso = confini_y[riga + 1] if riga == 0 else 0.40
        etichetta_sx, calcolo_sx, _ = righe_doppie[riga * 2]
        etichetta_dx, calcolo_dx, _ = righe_doppie[riga * 2 + 1]
        valore_sx, colore_sx = calcolo_sx(stato)
        valore_dx, colore_dx = calcolo_dx(stato)
        _tessera_mpl(ax, (0.0, y_basso, 0.49, y_alto), valore_sx, etichetta_sx, colore_sx)
        _tessera_mpl(ax, (0.51, y_basso, 1.0, y_alto), valore_dx, etichetta_dx, colore_dx)

    etichetta, calcolo, _ = piena
    valore, colore = calcolo(stato)
    _tessera_mpl(ax, (0.0, 0.28, 1.0, 0.40), valore, etichetta, colore)

    for i, (etichetta, calcolo) in enumerate(_TESSERE_PICCOLE):
        x0 = 0.0 if i == 0 else 0.51
        x1 = 0.49 if i == 0 else 1.0
        _tessera_mpl(ax, (x0, 0.0, x1, 0.22), calcolo(stato), etichetta, c.COLORI["grigio"], piccola=True)


def _disegna_barra_obiettivo_mpl(ax, stato: c.Stato) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    percento = stato.progresso
    ax.text(0.0, 0.92, "Verso i 5.000", fontsize=9, color="#5F5F5F", va="top")
    ax.text(
        1.0,
        0.92,
        f"{c.euro(stato.patrimonio)} di {c.euro(c.OBIETTIVO)} · {round(percento * 100)}%",
        fontsize=9,
        color="#5F5F5F",
        va="top",
        ha="right",
    )
    altezza_barra = 0.38
    raggio = altezza_barra / 2
    ax.add_patch(
        FancyBboxPatch(
            (0.0, 0.08),
            1.0,
            altezza_barra,
            boxstyle=f"round,pad=0,rounding_size={raggio}",
            linewidth=0,
            facecolor=_hex_a_rgba01(c.COLORI["arancione"], 0.18),
        )
    )
    if percento > 0:
        # Il raggio degli angoli non puo' superare meta' della larghezza del
        # riempimento, altrimenti con una percentuale piccola la forma si
        # deforma invece di restare un pillola arrotondata.
        larghezza = max(percento, 0.02)
        raggio_riempimento = min(raggio, larghezza / 2)
        ax.add_patch(
            FancyBboxPatch(
                (0.0, 0.08),
                larghezza,
                altezza_barra,
                boxstyle=f"round,pad=0,rounding_size={raggio_riempimento}",
                linewidth=0,
                facecolor=c.COLORI["arancione"],
            )
        )


def _asse_vuoto(ax, messaggio: str) -> None:
    ax.set_facecolor("white")
    ax.axis("off")
    ax.text(0.5, 0.5, messaggio, ha="center", va="center", fontsize=10, color="#8A8A8A", transform=ax.transAxes)


def _stile_assi_mpl(ax, date_in_x: bool = False) -> None:
    for lato in ("top", "right", "left"):
        ax.spines[lato].set_visible(False)
    ax.spines["bottom"].set_color(_GRIGIO_RECESSIVO)
    ax.tick_params(colors="#8A8A8A", labelsize=8)
    ax.grid(axis="y", color=_GRIGIO_RECESSIVO, linewidth=0.8)
    ax.set_axisbelow(True)
    if date_in_x:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    for etichetta in ax.get_xticklabels():
        etichetta.set_rotation(30)
        etichetta.set_ha("right")
        etichetta.set_rotation_mode("anchor")


def _tacche_mpl(ax, xs, etichette) -> None:
    tacche_x, tacche_testo = _tacche_diradate(xs, etichette)
    ax.set_xticks(tacche_x)
    ax.set_xticklabels(tacche_testo)


def _disegna_andamento_mpl(ax, stato: c.Stato) -> None:
    ax.set_facecolor("white")
    ax.set_title("Andamento del portafoglio", loc="left", fontsize=11, fontweight="bold", color=c.COLORI["testo"])
    serie_completa = stato.serie
    if len(serie_completa) < 2:
        _asse_vuoto(ax, "Ancora nessuna operazione da mostrare.")
        return

    serie = serie_completa[1:]
    xs, etichette = _punti_indice(serie)
    capitale = [p.capitale for p in serie]
    patrimonio = [p.patrimonio for p in serie]

    ax.plot(xs, capitale, color=c.COLORI["azzurro"], linewidth=2.0, label="Capitale versato")

    indici_versamento = [
        i for i in range(len(capitale)) if capitale[i] > (capitale[i - 1] if i > 0 else 0)
    ]
    if indici_versamento:
        ax.scatter(
            [xs[i] for i in indici_versamento],
            [capitale[i] for i in indici_versamento],
            color=c.COLORI["blu"],
            s=40,
            zorder=5,
            edgecolors="white",
            linewidths=1.2,
            label="Versamento",
        )

    ax.plot(xs, patrimonio, color=c.COLORI["arancione"], linewidth=2.2, label="Patrimonio")

    ultimo = serie[-1]
    scarto = ultimo.patrimonio - ultimo.capitale
    percento = 100 * scarto / ultimo.capitale if ultimo.capitale else 0.0
    # Il punto piu' recente e' sempre il piu' a destra: l'etichetta va verso
    # sinistra, altrimenti uscirebbe dal grafico.
    ax.annotate(
        f"{c.euro(ultimo.patrimonio)} ({percento:+.1f}%)",
        xy=(xs[-1], ultimo.patrimonio),
        xytext=(-6, 6 if scarto >= 0 else -6),
        textcoords="offset points",
        fontsize=8.5,
        color=c.colore_esito(scarto),
        ha="right",
        va="bottom" if scarto >= 0 else "top",
        bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=1.5),
    )

    ax.legend(loc="upper left", frameon=True, framealpha=0.8, edgecolor="none", fontsize=8)
    ax.margins(x=0.04, y=0.15)
    _tacche_mpl(ax, xs, etichette)
    _stile_assi_mpl(ax)


def _disegna_trade_mpl(ax, stato: c.Stato) -> None:
    ax.set_facecolor("white")
    ax.set_title("Trade chiusi", loc="left", fontsize=11, fontweight="bold", color=c.COLORI["testo"])
    trades = stato.trade_chiusi
    if not trades:
        _asse_vuoto(ax, "Ancora nessun trade chiuso.")
        return

    posizioni = list(range(len(trades)))
    colori = [c.colore_esito(t.netto) for t in trades]
    ax.bar(posizioni, [t.netto for t in trades], color=colori, width=0.6)
    # Con tanti trade, un'etichetta per barra diventa illeggibile: ne mostro
    # al massimo una quindicina, a passi regolari.
    passo = max(1, -(-len(trades) // 15))
    mostrate = posizioni[::passo]
    ax.set_xticks(mostrate)
    ax.set_xticklabels([c.data_testo(trades[i].data_chiusura) for i in mostrate])
    ax.axhline(0, color=_GRIGIO_RECESSIVO, linewidth=0.8)
    _stile_assi_mpl(ax)


def _disegna_torta_mpl(ax, stato: c.Stato) -> None:
    ax.set_facecolor("white")
    ax.axis("off")
    ax.set_title("Posizioni aperte e liquidità", loc="left", fontsize=11, fontweight="bold", color=c.COLORI["testo"])

    etichette = [p.prodotto for p in stato.posizioni]
    valori = [p.investito for p in stato.posizioni]
    colori = [PALETTE_TORTA[i % len(PALETTE_TORTA)] for i in range(len(stato.posizioni))]
    etichette.append("Liquidità")
    valori.append(max(stato.liquidita, 0.0))
    colori.append(LIQUIDITA_COLORE)

    if sum(valori) <= 0:
        _asse_vuoto(ax, "Nessuna posizione aperta.")
        return

    ax.pie(
        valori,
        labels=etichette,
        colors=colori,
        autopct="%1.0f%%",
        textprops={"color": c.COLORI["testo"], "fontsize": 8},
        wedgeprops={"linewidth": 2, "edgecolor": "white"},
    )


_COLONNE_TABELLA = (
    ("Data", 0.0, "left"),
    ("Operazione", 0.14, "left"),
    ("Dettaglio", 0.50, "left"),
    ("Lordo", 0.73, "right"),
    ("Tasse", 0.84, "right"),
    ("Netto", 0.97, "right"),
)


def _riga_tabella(riga: c.Riga):
    """(testo_operazione, testo_dettaglio, (lordo, colore), (tasse, colore), (netto, colore))."""
    grigio = "#5F5F5F"
    if riga.tipo == c.VERSAMENTO:
        return f"Verso capitale", c.euro(riga.importo), ("", grigio), ("", grigio), ("", grigio)
    if riga.tipo == c.ACQUISTO:
        dettaglio = f"{c.quote_testo(riga.operazione.quote)} quote a {c.euro(riga.operazione.prezzo)}"
        return f"Compro {riga.prodotto}", dettaglio, ("", grigio), ("", grigio), ("", grigio)
    dettaglio = f"{c.quote_testo(riga.operazione.quote)} quote a {c.euro(riga.operazione.prezzo)}"
    if riga.lordo is None:
        return f"Vendo {riga.prodotto}", dettaglio, ("—", grigio), ("—", grigio), ("—", grigio)
    colore = c.colore_esito(riga.lordo)
    return (
        f"Vendo {riga.prodotto}",
        dettaglio,
        (c.euro(riga.lordo, segno=True), colore),
        (c.euro(riga.tasse), grigio),
        (c.euro(riga.netto, segno=True), colore),
    )


def _disegna_tabella_mpl(ax, stato: c.Stato) -> None:
    ax.set_facecolor("none")
    ax.axis("off")
    righe = list(reversed(stato.righe))
    n = len(righe)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, n + 1)

    if not righe:
        ax.text(0.5, 0.5, "Non c'è ancora nessuna operazione.", ha="center", va="center", fontsize=10, color="#8A8A8A")
        return

    for titolo, x, allineamento in _COLONNE_TABELLA:
        ax.text(x, n + 0.4, titolo, fontsize=8, fontweight="bold", color="#5F5F5F", ha=allineamento)
    ax.axhline(n + 0.05, color=_GRIGIO_RECESSIVO, linewidth=0.8, xmax=1.0)

    for i, riga in enumerate(righe):
        y = n - i - 0.5
        operazione, dettaglio, lordo, tasse, netto = _riga_tabella(riga)
        ax.text(0.0, y, c.data_testo(riga.data), fontsize=8, color=c.COLORI["testo"], va="center")
        ax.text(0.14, y, operazione, fontsize=8, color=c.COLORI["testo"], va="center")
        ax.text(0.50, y, dettaglio, fontsize=8, color="#5F5F5F", va="center")
        ax.text(0.73, y, lordo[0], fontsize=8, color=lordo[1], va="center", ha="right", fontweight="bold")
        ax.text(0.84, y, tasse[0], fontsize=8, color=tasse[1], va="center", ha="right")
        ax.text(0.97, y, netto[0], fontsize=8, color=netto[1], va="center", ha="right", fontweight="bold")


def immagine_dashboard(stato: c.Stato, oggi: date | None = None) -> bytes:
    """Il PNG completo della dashboard: una sola figura verticale.

    L'altezza cresce con il numero di operazioni, cosi' non si taglia nulla
    anche con uno storico lungo.
    """
    oggi = oggi or date.today()
    n_righe = len(stato.righe)

    altezze = {
        "intestazione": 0.6,
        "numeri": 2.5,
        "barra": 0.45,
        "andamento": 2.6,
        "trade": 2.1,
        "torta": 2.6,
        "tabella": 0.55 + 0.26 * max(n_righe, 1),
    }
    altezza_totale = sum(altezze.values())
    larghezza = 8.0

    fig = plt.figure(figsize=(larghezza, altezza_totale), dpi=160, facecolor=c.COLORI["crema"])

    cursore = 0.0

    def aggiungi(nome, margine=0.05, pad_sopra_in=0.0, pad_sotto_in=0.0):
        """Il riquadro della prossima sezione, scendendo dall'alto.

        pad_sopra_in/pad_sotto_in riservano dello spazio DENTRO la sezione (in
        pollici) per il titolo e per le etichette ruotate delle date: senza,
        matplotlib le disegna comunque, ma fuori dal riquadro, sopra la
        sezione precedente o sotto quella successiva.
        """
        nonlocal cursore
        altezza = altezze[nome]
        cursore += altezza
        y0_sezione = 1 - cursore / altezza_totale
        y0 = y0_sezione + pad_sotto_in / altezza_totale
        h = (altezza - pad_sopra_in - pad_sotto_in) / altezza_totale
        return fig.add_axes((margine, y0, 1 - 2 * margine, h))

    _disegna_intestazione_mpl(aggiungi("intestazione", margine=0.04), oggi)
    _disegna_numeri_mpl(aggiungi("numeri", margine=0.04), stato)
    _disegna_barra_obiettivo_mpl(aggiungi("barra", margine=0.05), stato)
    _disegna_andamento_mpl(
        aggiungi("andamento", margine=0.08, pad_sopra_in=0.32, pad_sotto_in=0.5), stato
    )
    _disegna_trade_mpl(aggiungi("trade", margine=0.08, pad_sopra_in=0.32, pad_sotto_in=0.5), stato)
    _disegna_torta_mpl(aggiungi("torta", margine=0.14, pad_sopra_in=0.32, pad_sotto_in=0.05), stato)
    _disegna_tabella_mpl(aggiungi("tabella", margine=0.03), stato)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()
