"""Tutta la logica di «Verso i 5.000»: PMC, lordo, tasse, perdite da
compensare, liquidita' e patrimonio.

Questo modulo non importa Streamlit e non legge nulla da disco: sono tutte
funzioni pure. L'app salva soltanto le operazioni e chiama `ricalcola` ogni
volta che si apre, cosi' correggere o cancellare una riga non rompe mai i
conti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

# --- Costanti ---------------------------------------------------------------

COMMISSIONE_DEFAULT = 1.0
ALIQUOTA_TASSE = 0.26
ANNI_COMPENSAZIONE = 4
OBIETTIVO = 5000.0

# I colori della guida, in un posto solo: li usano sia l'interfaccia sia i grafici.
COLORI = {
    "blu": "#2B7BBF",
    "arancione": "#F28A1E",
    "crema": "#FEF1E2",
    "azzurro": "#7EC8E3",
    "verde": "#2E9E5B",
    "rosso": "#D64545",
    "grigio": "#9AA0A6",
    "testo": "#2A2A2A",
}

VERSAMENTO = "versamento"
ACQUISTO = "acquisto"
VENDITA = "vendita"
TIPI = (VERSAMENTO, ACQUISTO, VENDITA)

GAIN = "gain"
LOSS = "loss"
PARI = "pari"

_CENTESIMO = Decimal("0.01")
# Sotto questa soglia le quote residue di una posizione sono considerate zero:
# serve solo a proteggere dagli arrotondamenti dei numeri decimali.
_TOLLERANZA_QUOTE = 1e-9


# --- Arrotondamenti e formati ----------------------------------------------


def arrotonda(valore: float) -> float:
    """Arrotonda al centesimo: mezzo centesimo si allontana da zero.

    0,125 diventa 0,13 e -0,125 diventa -0,13, cosi' un gain e una loss della
    stessa misura vengono arrotondati nello stesso modo.
    """
    return float(Decimal(str(float(valore))).quantize(_CENTESIMO, rounding=ROUND_HALF_UP))


def normalizza_nome(prodotto: str) -> str:
    """Chiave con cui l'app riconosce lo stesso prodotto.

    Ignora le maiuscole e gli spazi doppi: "coinbase  5x long" e
    "Coinbase 5x long" sono lo stesso prodotto.
    """
    return " ".join(str(prodotto or "").split()).casefold()


def nome_pulito(prodotto: str) -> str:
    """Il nome come viene mostrato: spazi doppi tolti, maiuscole rispettate."""
    return " ".join(str(prodotto or "").split())


def esito(valore: float) -> str:
    """gain se sopra zero, loss se sotto, pari se esattamente zero."""
    if valore > 0:
        return GAIN
    if valore < 0:
        return LOSS
    return PARI


def numero(valore: float, decimali: int = 2) -> str:
    """Numero con la virgola decimale e il punto per le migliaia."""
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", " ").replace(".", ",").replace(" ", ".")


def euro(valore: float, segno: bool = False) -> str:
    """Importo in euro: 3,37 € oppure +0,64 € se chiedi il segno."""
    valore = arrotonda(valore)
    if valore == 0:
        valore = 0.0  # evita "-0,00 €"
    prefisso = "+" if segno and valore > 0 else ""
    return f"{prefisso}{numero(valore)} €"


def quote_testo(quote: float) -> str:
    """Le quote: "9" se sono intere, "9,5" se no."""
    if abs(quote - round(quote)) < _TOLLERANZA_QUOTE:
        return numero(round(quote), 0)
    return numero(quote, 4).rstrip("0").rstrip(",")


def data_testo(giorno: date) -> str:
    """Data in formato gg/mm/aaaa."""
    return giorno.strftime("%d/%m/%Y")


def colore_esito(valore: float) -> str:
    """Verde se sopra zero, rosso se sotto, grigio se esattamente zero."""
    return {GAIN: COLORI["verde"], LOSS: COLORI["rosso"], PARI: COLORI["grigio"]}[
        esito(valore)
    ]


def leggi_numero(testo):
    """Legge un numero scritto come si scrive in italiano.

    Accetta "3,50", "3.50", "1.234,56" e anche "3,50 €". Torna None se il
    campo e' vuoto o non si capisce.
    """
    if testo is None:
        return None
    if isinstance(testo, (int, float)):
        return float(testo)
    pulito = str(testo).strip().replace("€", "").replace(" ", "").replace(" ", "")
    if not pulito:
        return None
    if "," in pulito:
        # La virgola e' il separatore decimale: i punti sono le migliaia.
        pulito = pulito.replace(".", "").replace(",", ".")
    try:
        return float(pulito)
    except ValueError:
        return None


def a_data(valore) -> date:
    """Accetta una data, un datetime o una stringa aaaa-mm-gg / gg/mm/aaaa."""
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    testo = str(valore).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(testo, formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data non riconosciuta: {valore!r}")


# --- Le operazioni salvate --------------------------------------------------


@dataclass(frozen=True)
class Operazione:
    """Una riga del file delle operazioni: l'unico dato che l'app salva."""

    id: int
    data: date
    tipo: str
    prodotto: str = ""
    quote: float = 0.0
    prezzo: float = 0.0
    commissione: float = 0.0
    nota: str = ""

    @property
    def chiave(self) -> str:
        return normalizza_nome(self.prodotto)

    @classmethod
    def da_dict(cls, dati: dict) -> "Operazione":
        return cls(
            id=int(dati["id"]),
            data=a_data(dati["data"]),
            tipo=str(dati["tipo"]).strip().casefold(),
            prodotto=nome_pulito(dati.get("prodotto", "")),
            quote=float(dati.get("quote") or 0.0),
            prezzo=float(dati.get("prezzo") or 0.0),
            commissione=float(dati.get("commissione") or 0.0),
            nota=str(dati.get("nota") or "").strip(),
        )

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "data": self.data.isoformat(),
            "tipo": self.tipo,
            "prodotto": self.prodotto,
            "quote": self.quote,
            "prezzo": self.prezzo,
            "commissione": self.commissione,
            "nota": self.nota,
        }


def ordina(operazioni) -> list:
    """In ordine di data; a pari data vale l'ordine in cui sono state segnate."""
    return sorted(operazioni, key=lambda o: (o.data, o.id))


# --- I risultati del ricalcolo ---------------------------------------------


@dataclass
class LottoPerdita:
    """Una perdita da compensare, con l'anno in cui e' nata."""

    anno: int
    importo: float
    residuo: float

    @property
    def scadenza(self) -> date:
        return date(self.anno + ANNI_COMPENSAZIONE, 12, 31)

    def valido_il(self, giorno: date) -> bool:
        return giorno <= self.scadenza


@dataclass
class Posizione:
    """Un prodotto comprato e non ancora venduto del tutto."""

    prodotto: str
    chiave: str
    quote: float
    pmc: float
    commissioni_acquisto_residue: float
    data_apertura: date

    @property
    def investito(self) -> float:
        """Quanto vale al prezzo medio di carico: quote x PMC."""
        return arrotonda(self.quote * self.pmc)


@dataclass
class TradeChiuso:
    """Una posizione dall'apertura fino a quando le quote tornano a zero."""

    prodotto: str
    data_apertura: date
    data_chiusura: date
    lordo: float
    tasse: float
    netto: float
    esito: str
    vendite: int


@dataclass
class Riga:
    """Un'operazione con accanto tutto quello che l'app calcola da sola."""

    operazione: Operazione
    liquidita_dopo: float = 0.0
    patrimonio_dopo: float = 0.0
    errore: str = ""
    # versamento
    importo: float | None = None
    # acquisto
    costo: float | None = None
    quote_dopo: float | None = None
    pmc_dopo: float | None = None
    # vendita
    incasso: float | None = None
    pmc: float | None = None
    lordo: float | None = None
    perdite_usate: float | None = None
    tasse: float | None = None
    netto: float | None = None
    esito_vendita: str | None = None
    quote_restanti: float | None = None
    chiude_posizione: bool = False

    @property
    def data(self) -> date:
        return self.operazione.data

    @property
    def tipo(self) -> str:
        return self.operazione.tipo

    @property
    def prodotto(self) -> str:
        return self.operazione.prodotto


@dataclass
class Punto:
    """Un punto delle linee dei grafici."""

    data: date
    capitale: float
    lordo: float
    netto: float
    patrimonio: float
    liquidita: float


@dataclass
class Stato:
    """La fotografia completa del conto dopo tutte le operazioni."""

    oggi: date
    righe: list = field(default_factory=list)
    posizioni: list = field(default_factory=list)
    trade_chiusi: list = field(default_factory=list)
    lotti_perdite: list = field(default_factory=list)
    serie: list = field(default_factory=list)
    capitale_versato: float = 0.0
    liquidita: float = 0.0
    patrimonio: float = 0.0
    lordo_totale: float = 0.0
    tasse_totali: float = 0.0
    netto_totale: float = 0.0
    perdite_da_compensare: float = 0.0

    def posizione(self, prodotto: str) -> Posizione | None:
        chiave = normalizza_nome(prodotto)
        for posizione in self.posizioni:
            if posizione.chiave == chiave:
                return posizione
        return None

    def nomi_posizioni(self) -> list:
        return [posizione.prodotto for posizione in self.posizioni]

    def riga(self, id_operazione: int) -> Riga | None:
        for riga in self.righe:
            if riga.operazione.id == id_operazione:
                return riga
        return None

    @property
    def investito(self) -> float:
        return arrotonda(sum(p.investito for p in self.posizioni))

    @property
    def esito_totale(self) -> str:
        return esito(self.netto_totale)

    @property
    def progresso(self) -> float:
        """Quanta strada verso i 5.000, da 0 a 1."""
        return max(0.0, min(1.0, self.patrimonio / OBIETTIVO))


# --- Il ricalcolo -----------------------------------------------------------


@dataclass
class _Aperta:
    """Stato interno di una posizione mentre il ricalcolo avanza."""

    prodotto: str
    quote: float
    pmc: float
    commissioni: float
    data_apertura: date
    lordo: float = 0.0
    tasse: float = 0.0
    netto: float = 0.0
    vendite: int = 0


def _usa_perdite(lotti: list, lordo: float, giorno: date) -> float:
    """Consuma le perdite ancora valide, dalla piu' vecchia. Torna quante ne usa."""
    usate = 0.0
    restante = lordo
    for lotto in lotti:
        if restante <= 0:
            break
        if lotto.residuo <= 0 or not lotto.valido_il(giorno):
            continue
        preso = min(lotto.residuo, restante)
        lotto.residuo = arrotonda(lotto.residuo - preso)
        usate += preso
        restante = arrotonda(restante - preso)
    return arrotonda(usate)


def ricalcola(operazioni, oggi: date | None = None) -> Stato:
    """Rifa' tutti i conti partendo dalle sole operazioni salvate."""
    oggi = oggi or date.today()
    stato = Stato(oggi=oggi)

    aperte: dict = {}
    capitale = 0.0
    liquidita = 0.0
    lordo_totale = 0.0
    tasse_totali = 0.0
    netto_totale = 0.0

    elenco = ordina(operazioni)
    if elenco:
        stato.serie.append(
            Punto(data=elenco[0].data, capitale=0.0, lordo=0.0, netto=0.0, patrimonio=0.0, liquidita=0.0)
        )

    for operazione in elenco:
        riga = Riga(operazione=operazione)

        if operazione.tipo == VERSAMENTO:
            importo = arrotonda(operazione.prezzo)
            capitale = arrotonda(capitale + importo)
            liquidita = arrotonda(liquidita + importo)
            riga.importo = importo

        elif operazione.tipo == ACQUISTO:
            quote = operazione.quote
            prezzo = operazione.prezzo
            commissione = operazione.commissione
            chiave = operazione.chiave
            posizione = aperte.get(chiave)
            if posizione is None:
                posizione = _Aperta(
                    prodotto=operazione.prodotto,
                    quote=quote,
                    pmc=prezzo,
                    commissioni=commissione,
                    data_apertura=operazione.data,
                )
                aperte[chiave] = posizione
            else:
                totale_quote = posizione.quote + quote
                posizione.pmc = (posizione.quote * posizione.pmc + quote * prezzo) / totale_quote
                posizione.quote = totale_quote
                posizione.commissioni += commissione
            costo = arrotonda(quote * prezzo + commissione)
            liquidita = arrotonda(liquidita - costo)
            riga.costo = costo
            riga.quote_dopo = posizione.quote
            riga.pmc_dopo = posizione.pmc

        elif operazione.tipo == VENDITA:
            posizione = aperte.get(operazione.chiave)
            if posizione is None:
                riga.errore = f"Non ci sono quote aperte di {operazione.prodotto}."
            else:
                quote = operazione.quote
                if quote > posizione.quote + _TOLLERANZA_QUOTE:
                    riga.errore = (
                        f"{quote_testo(posizione.quote)} quote disponibili di "
                        f"{posizione.prodotto}, vendute {quote_testo(quote)}."
                    )
                    quote = posizione.quote
                commissione = operazione.commissione
                pmc = posizione.pmc
                commissioni_acquisto = posizione.commissioni * quote / posizione.quote
                risultato = (
                    (operazione.prezzo - pmc) * quote - commissione - commissioni_acquisto
                )
                lordo = arrotonda(risultato)

                if lordo > 0:
                    perdite_usate = _usa_perdite(stato.lotti_perdite, lordo, operazione.data)
                    tasse = arrotonda(ALIQUOTA_TASSE * (lordo - perdite_usate))
                else:
                    perdite_usate = 0.0
                    tasse = 0.0
                    if lordo < 0:
                        stato.lotti_perdite.append(
                            LottoPerdita(
                                anno=operazione.data.year,
                                importo=abs(lordo),
                                residuo=abs(lordo),
                            )
                        )
                netto = arrotonda(lordo - tasse)

                incasso = arrotonda(quote * operazione.prezzo - commissione)
                liquidita = arrotonda(liquidita + incasso - tasse)
                lordo_totale = arrotonda(lordo_totale + lordo)
                tasse_totali = arrotonda(tasse_totali + tasse)
                netto_totale = arrotonda(netto_totale + netto)

                posizione.quote = posizione.quote - quote
                posizione.commissioni = posizione.commissioni - commissioni_acquisto
                posizione.lordo += lordo
                posizione.tasse += tasse
                posizione.netto += netto
                posizione.vendite += 1

                riga.incasso = incasso
                riga.pmc = pmc
                riga.lordo = lordo
                riga.perdite_usate = perdite_usate
                riga.tasse = tasse
                riga.netto = netto
                riga.esito_vendita = esito(lordo)
                riga.quote_restanti = posizione.quote

                if posizione.quote <= _TOLLERANZA_QUOTE:
                    riga.chiude_posizione = True
                    riga.quote_restanti = 0.0
                    netto_trade = arrotonda(posizione.netto)
                    stato.trade_chiusi.append(
                        TradeChiuso(
                            prodotto=posizione.prodotto,
                            data_apertura=posizione.data_apertura,
                            data_chiusura=operazione.data,
                            lordo=arrotonda(posizione.lordo),
                            tasse=arrotonda(posizione.tasse),
                            netto=netto_trade,
                            esito=esito(netto_trade),
                            vendite=posizione.vendite,
                        )
                    )
                    del aperte[operazione.chiave]

        else:
            riga.errore = f"Tipo di operazione sconosciuto: {operazione.tipo!r}."

        patrimonio = arrotonda(capitale + netto_totale)
        riga.liquidita_dopo = liquidita
        riga.patrimonio_dopo = patrimonio
        stato.righe.append(riga)
        stato.serie.append(
            Punto(
                data=operazione.data,
                capitale=capitale,
                lordo=lordo_totale,
                netto=netto_totale,
                patrimonio=patrimonio,
                liquidita=liquidita,
            )
        )

    stato.posizioni = [
        Posizione(
            prodotto=posizione.prodotto,
            chiave=chiave,
            quote=posizione.quote,
            pmc=posizione.pmc,
            commissioni_acquisto_residue=arrotonda(posizione.commissioni),
            data_apertura=posizione.data_apertura,
        )
        for chiave, posizione in aperte.items()
    ]
    stato.capitale_versato = capitale
    stato.liquidita = liquidita
    stato.lordo_totale = lordo_totale
    stato.tasse_totali = tasse_totali
    stato.netto_totale = netto_totale
    stato.patrimonio = arrotonda(capitale + netto_totale)
    stato.perdite_da_compensare = arrotonda(
        sum(lotto.residuo for lotto in stato.lotti_perdite if lotto.valido_il(oggi))
    )
    return stato


# --- Controlli prima di salvare -------------------------------------------


def _precedenti(operazioni, nuova: Operazione) -> list:
    """Le operazioni che vengono prima di `nuova` nell'ordine cronologico."""
    return [
        o
        for o in ordina(operazioni)
        if o.id != nuova.id and (o.data, o.id) < (nuova.data, nuova.id)
    ]


def valida(operazioni, nuova: Operazione, blocca_liquidita: bool = True) -> list:
    """Gli errori che impediscono di salvare `nuova`, in italiano.

    Lista vuota se l'operazione si puo' salvare.
    """
    errori = []

    if nuova.tipo not in TIPI:
        return [f"Tipo di operazione sconosciuto: {nuova.tipo!r}."]

    if nuova.tipo == VERSAMENTO:
        if nuova.prezzo <= 0:
            errori.append("Scrivi quanto hai versato.")
        return errori

    if not normalizza_nome(nuova.prodotto):
        errori.append("Scrivi il nome del prodotto.")
    if nuova.quote <= 0:
        errori.append("Scrivi quante quote.")
    if nuova.prezzo <= 0:
        errori.append("Scrivi il prezzo di ogni quota.")
    if errori:
        return errori

    prima = ricalcola(_precedenti(operazioni, nuova), oggi=nuova.data)

    if nuova.tipo == ACQUISTO:
        costo = arrotonda(nuova.quote * nuova.prezzo + nuova.commissione)
        if blocca_liquidita and costo > prima.liquidita:
            errori.append(
                f"Per questo acquisto servono {euro(costo)} ma hai liberi "
                f"{euro(prima.liquidita)}: manca un versamento?"
            )
        return errori

    posizione = prima.posizione(nuova.prodotto)
    if posizione is None:
        errori.append(
            f"Non hai quote aperte di {nome_pulito(nuova.prodotto)}: "
            "scegli un prodotto dalle tue posizioni aperte."
        )
    elif nuova.quote > posizione.quote + _TOLLERANZA_QUOTE:
        errori.append(
            f"Hai {quote_testo(posizione.quote)} quote di {posizione.prodotto}: "
            f"non puoi venderne {quote_testo(nuova.quote)}."
        )
    return errori


def anteprima(operazioni, nuova: Operazione):
    """Il riepilogo da mostrare prima di Salva, calcolato come il ricalcolo vero.

    Torna la riga dell'operazione nuova e lo stato del conto dopo di essa.
    """
    stato = ricalcola(list(operazioni) + [nuova], oggi=nuova.data)
    return stato.riga(nuova.id), stato


def prossimo_id(operazioni) -> int:
    """L'id da dare alla prossima operazione: tiene l'ordine di inserimento."""
    return max((o.id for o in operazioni), default=0) + 1
