"""I test della logica di «Verso i 5.000».

Seguono l'esempio Coinbase del manuale e le regole fiscali dell'appendice.
"""

from datetime import date

import pytest

import calcoli as c
from calcoli import Operazione


# --- Un piccolo diario per scrivere i test come si segnano le operazioni ----


class Diario:
    """Costruisce la lista di operazioni con gli id nell'ordine di inserimento."""

    def __init__(self):
        self.operazioni = []

    def _aggiungi(self, **dati) -> Operazione:
        operazione = Operazione(id=c.prossimo_id(self.operazioni), **dati)
        self.operazioni.append(operazione)
        return operazione

    def versa(self, giorno, importo):
        return self._aggiungi(data=giorno, tipo=c.VERSAMENTO, prezzo=importo)

    def compra(self, giorno, prodotto, quote, prezzo, commissione=c.COMMISSIONE_DEFAULT):
        return self._aggiungi(
            data=giorno,
            tipo=c.ACQUISTO,
            prodotto=prodotto,
            quote=quote,
            prezzo=prezzo,
            commissione=commissione,
        )

    def vendi(self, giorno, prodotto, quote, prezzo, commissione=c.COMMISSIONE_DEFAULT):
        return self._aggiungi(
            data=giorno,
            tipo=c.VENDITA,
            prodotto=prodotto,
            quote=quote,
            prezzo=prezzo,
            commissione=commissione,
        )

    def stato(self, fino_a=None, oggi=None) -> c.Stato:
        operazioni = self.operazioni if fino_a is None else self.operazioni[:fino_a]
        return c.ricalcola(operazioni, oggi=oggi or date(2026, 12, 31))

    def senza(self, operazione) -> list:
        return [o for o in self.operazioni if o.id != operazione.id]

    def con_modifica(self, operazione, **cambi) -> list:
        import dataclasses

        return [
            dataclasses.replace(o, **cambi) if o.id == operazione.id else o
            for o in self.operazioni
        ]


COINBASE = "Coinbase 5x long"


@pytest.fixture
def coinbase():
    """L'esempio del manuale: capitale 250 €, due acquisti e due vendite."""
    diario = Diario()
    diario.versa(date(2026, 10, 1), 250.0)
    diario.compra(date(2026, 10, 5), COINBASE, 5, 3.50)
    diario.compra(date(2026, 10, 9), COINBASE, 4, 3.20)
    diario.vendi(date(2026, 10, 15), COINBASE, 4, 4.00)
    diario.vendi(date(2026, 10, 20), COINBASE, 5, 4.20)
    return diario


def perdita_di_150(diario, giorno_acquisto, giorno_vendita, prodotto="Tesla 3x long"):
    """Un trade chiuso con un lordo di esattamente -1,50 €."""
    diario.compra(giorno_acquisto, prodotto, 1, 10.00)
    diario.vendi(giorno_vendita, prodotto, 1, 10.50)


def gain_di_100(diario, giorno_acquisto, giorno_vendita, prodotto="Nvidia 3x long"):
    """Un trade chiuso con un lordo di esattamente +1,00 €."""
    diario.compra(giorno_acquisto, prodotto, 1, 10.00)
    diario.vendi(giorno_vendita, prodotto, 1, 13.00)


# --- 1. I due acquisti: quote e PMC ----------------------------------------


def test_primo_acquisto(coinbase):
    stato = coinbase.stato(fino_a=2)
    posizione = stato.posizione(COINBASE)
    assert posizione.quote == 5
    assert posizione.pmc == pytest.approx(3.50)
    assert stato.liquidita == 231.50  # 250 - (5 x 3,50 + 1)


def test_secondo_acquisto_fa_la_media(coinbase):
    stato = coinbase.stato(fino_a=3)
    posizione = stato.posizione(COINBASE)
    assert posizione.quote == 9
    assert posizione.pmc == pytest.approx(3.366666, abs=1e-5)
    assert c.arrotonda(posizione.pmc) == 3.37
    assert c.euro(posizione.pmc) == "3,37 €"
    # Le due commissioni d'acquisto non sono ancora state attribuite.
    assert posizione.commissioni_acquisto_residue == 2.00
    assert stato.liquidita == 217.70


# --- 2. La prima vendita ----------------------------------------------------


def test_vendita_parziale(coinbase):
    stato = coinbase.stato(fino_a=4)
    riga = stato.righe[-1]
    assert riga.lordo == 0.64
    assert riga.tasse == 0.17
    assert riga.netto == 0.47
    assert riga.esito_vendita == c.GAIN
    assert riga.perdite_usate == 0.0
    assert riga.chiude_posizione is False

    posizione = stato.posizione(COINBASE)
    assert posizione.quote == 5
    assert posizione.pmc == pytest.approx(3.366666, abs=1e-5)  # il PMC non cambia
    assert posizione.commissioni_acquisto_residue == pytest.approx(1.11, abs=0.005)


# --- 3. La seconda vendita chiude la posizione -----------------------------


def test_vendita_finale_chiude_la_posizione(coinbase):
    stato = coinbase.stato()
    riga = stato.righe[-1]
    assert riga.lordo == 2.06
    assert riga.tasse == 0.54
    assert riga.netto == 1.52
    assert riga.chiude_posizione is True
    assert riga.quote_restanti == 0.0

    assert stato.posizioni == []
    assert stato.posizione(COINBASE) is None


# --- 4. I totali ------------------------------------------------------------


def test_totali_dell_esempio(coinbase):
    stato = coinbase.stato()
    assert stato.lordo_totale == 2.70
    assert stato.tasse_totali == 0.71
    assert stato.netto_totale == 1.99
    assert stato.capitale_versato == 250.00
    assert stato.liquidita == 251.99
    assert stato.patrimonio == 251.99
    assert stato.perdite_da_compensare == 0.0


def test_un_solo_trade_chiuso_con_il_netto_del_manuale(coinbase):
    stato = coinbase.stato()
    assert len(stato.trade_chiusi) == 1
    trade = stato.trade_chiusi[0]
    assert trade.prodotto == COINBASE
    assert trade.lordo == 2.70
    assert trade.netto == 1.99
    assert trade.esito == c.GAIN
    assert trade.vendite == 2
    assert trade.data_apertura == date(2026, 10, 5)
    assert trade.data_chiusura == date(2026, 10, 20)


# --- 5. Lo stesso esempio con una loss precedente da compensare ------------


@pytest.fixture
def coinbase_con_perdita():
    diario = Diario()
    diario.versa(date(2026, 9, 1), 250.0)
    perdita_di_150(diario, date(2026, 9, 2), date(2026, 9, 3))
    diario.compra(date(2026, 10, 5), COINBASE, 5, 3.50)
    diario.compra(date(2026, 10, 9), COINBASE, 4, 3.20)
    diario.vendi(date(2026, 10, 15), COINBASE, 4, 4.00)
    diario.vendi(date(2026, 10, 20), COINBASE, 5, 4.20)
    return diario


def test_la_loss_non_paga_tasse_e_diventa_perdita_da_compensare(coinbase_con_perdita):
    stato = coinbase_con_perdita.stato(fino_a=3)
    riga = stato.righe[-1]
    assert riga.lordo == -1.50
    assert riga.tasse == 0.0
    assert riga.netto == -1.50
    assert riga.esito_vendita == c.LOSS
    assert stato.perdite_da_compensare == 1.50


def test_le_perdite_abbassano_le_tasse_delle_vendite_successive(coinbase_con_perdita):
    dopo_prima_vendita = coinbase_con_perdita.stato(fino_a=6)
    prima = dopo_prima_vendita.righe[-1]
    assert prima.lordo == 0.64
    assert prima.perdite_usate == 0.64
    assert prima.tasse == 0.00
    assert prima.netto == 0.64
    assert dopo_prima_vendita.perdite_da_compensare == 0.86

    stato = coinbase_con_perdita.stato()
    seconda = stato.righe[-1]
    assert seconda.lordo == 2.06
    assert seconda.perdite_usate == 0.86
    assert seconda.tasse == 0.31
    assert seconda.netto == 1.75
    assert stato.perdite_da_compensare == 0.00

    assert stato.lordo_totale == 1.20  # -1,50 + 0,64 + 2,06
    assert stato.tasse_totali == 0.31
    assert stato.netto_totale == 0.89
    assert stato.patrimonio == 250.89


# --- 6. Scadenza delle perdite e ordine di utilizzo ------------------------


def test_la_perdita_del_2026_scade_il_31_12_2030():
    diario = Diario()
    diario.versa(date(2026, 1, 1), 1000.0)
    perdita_di_150(diario, date(2026, 6, 2), date(2026, 6, 3))
    stato = diario.stato(oggi=date(2026, 12, 31))
    lotto = stato.lotti_perdite[0]
    assert lotto.anno == 2026
    assert lotto.scadenza == date(2030, 12, 31)
    assert lotto.valido_il(date(2030, 12, 31)) is True
    assert lotto.valido_il(date(2031, 1, 1)) is False
    # Dal 2031 l'app non la mostra piu' tra le perdite utilizzabili.
    assert diario.stato(oggi=date(2030, 12, 31)).perdite_da_compensare == 1.50
    assert diario.stato(oggi=date(2031, 1, 1)).perdite_da_compensare == 0.00


def test_la_perdita_del_2026_compensa_un_gain_del_2030():
    diario = Diario()
    diario.versa(date(2026, 1, 1), 1000.0)
    perdita_di_150(diario, date(2026, 6, 2), date(2026, 6, 3))
    gain_di_100(diario, date(2030, 12, 1), date(2030, 12, 30))
    stato = diario.stato(oggi=date(2030, 12, 31))
    vendita = stato.righe[-1]
    assert vendita.lordo == 1.00
    assert vendita.perdite_usate == 1.00
    assert vendita.tasse == 0.00
    assert vendita.netto == 1.00
    assert stato.perdite_da_compensare == 0.50


def test_la_perdita_del_2026_non_compensa_piu_un_gain_del_2031():
    diario = Diario()
    diario.versa(date(2026, 1, 1), 1000.0)
    perdita_di_150(diario, date(2026, 6, 2), date(2026, 6, 3))
    gain_di_100(diario, date(2030, 12, 1), date(2031, 1, 2))
    stato = diario.stato(oggi=date(2031, 1, 2))
    vendita = stato.righe[-1]
    assert vendita.lordo == 1.00
    assert vendita.perdite_usate == 0.00
    assert vendita.tasse == 0.26
    assert vendita.netto == 0.74
    assert stato.perdite_da_compensare == 0.00  # scaduta


def test_si_usano_prima_le_perdite_piu_vecchie():
    diario = Diario()
    diario.versa(date(2026, 1, 1), 1000.0)
    perdita_di_150(diario, date(2026, 6, 2), date(2026, 6, 3), "Perdita 2026")
    # Una seconda perdita, di 0,50 €, nata nel 2027.
    diario.compra(date(2027, 6, 2), "Perdita 2027", 1, 10.00)
    diario.vendi(date(2027, 6, 3), "Perdita 2027", 1, 11.50)
    gain_di_100(diario, date(2028, 6, 2), date(2028, 6, 3))

    stato = diario.stato(oggi=date(2028, 12, 31))
    assert [lotto.anno for lotto in stato.lotti_perdite] == [2026, 2027]
    assert stato.righe[-1].perdite_usate == 1.00
    # Consumata solo quella del 2026: restano 0,50 € di ciascuna.
    assert stato.lotti_perdite[0].residuo == 0.50
    assert stato.lotti_perdite[1].residuo == 0.50
    assert stato.perdite_da_compensare == 1.00


# --- 7. Una perdita compensa solo i guadagni venduti dopo di lei -----------


def test_il_gain_venduto_prima_della_perdita_paga_tutte_le_tasse():
    diario = Diario()
    diario.versa(date(2026, 1, 1), 1000.0)
    gain_di_100(diario, date(2026, 1, 2), date(2026, 1, 3))
    perdita_di_150(diario, date(2026, 1, 4), date(2026, 1, 5))

    stato = diario.stato()
    gain = stato.righe[2]
    assert gain.lordo == 1.00
    assert gain.perdite_usate == 0.00
    assert gain.tasse == 0.26
    assert gain.netto == 0.74

    assert stato.tasse_totali == 0.26  # non vengono restituite
    assert stato.lordo_totale == -0.50
    assert stato.netto_totale == -0.76
    assert stato.perdite_da_compensare == 1.50


# --- 8. Lordo esattamente zero: pari --------------------------------------


def test_lordo_zero_e_pari():
    diario = Diario()
    diario.versa(date(2026, 1, 1), 1000.0)
    diario.compra(date(2026, 1, 2), "Pari 2x long", 2, 5.00)
    diario.vendi(date(2026, 1, 3), "Pari 2x long", 2, 6.00)  # 2,00 - 1 - 1 = 0,00

    stato = diario.stato()
    vendita = stato.righe[-1]
    assert vendita.lordo == 0.00
    assert vendita.esito_vendita == c.PARI
    assert vendita.tasse == 0.00
    assert vendita.netto == 0.00
    assert stato.lotti_perdite == []  # un pari non crea perdite da compensare
    assert stato.perdite_da_compensare == 0.00
    assert stato.trade_chiusi[0].esito == c.PARI
    assert stato.patrimonio == 1000.00
    assert c.euro(vendita.lordo, segno=True) == "0,00 €"


# --- 9. Non si vende piu' di quello che si ha ------------------------------


def test_non_si_possono_vendere_piu_quote_di_quelle_possedute(coinbase):
    operazioni = coinbase.operazioni[:3]  # 9 quote aperte
    troppe = Operazione(
        id=c.prossimo_id(operazioni),
        data=date(2026, 10, 15),
        tipo=c.VENDITA,
        prodotto=COINBASE,
        quote=10,
        prezzo=4.00,
        commissione=1.0,
    )
    errori = c.valida(operazioni, troppe)
    assert len(errori) == 1
    assert "9 quote" in errori[0]
    assert "10" in errori[0]

    giuste = Operazione(**{**troppe.a_dict(), "data": date(2026, 10, 15), "quote": 9})
    assert c.valida(operazioni, giuste) == []


def test_non_si_vende_un_prodotto_che_non_si_ha(coinbase):
    operazioni = coinbase.operazioni  # posizione chiusa
    vendita = Operazione(
        id=c.prossimo_id(operazioni),
        data=date(2026, 10, 25),
        tipo=c.VENDITA,
        prodotto=COINBASE,
        quote=1,
        prezzo=4.00,
        commissione=1.0,
    )
    errori = c.valida(operazioni, vendita)
    assert len(errori) == 1
    assert "Non hai quote aperte" in errori[0]


def test_non_si_compra_oltre_la_liquidita(coinbase):
    operazioni = coinbase.operazioni[:1]  # solo il versamento da 250 €
    troppo = Operazione(
        id=c.prossimo_id(operazioni),
        data=date(2026, 10, 5),
        tipo=c.ACQUISTO,
        prodotto=COINBASE,
        quote=100,
        prezzo=3.50,
        commissione=1.0,
    )
    errori = c.valida(operazioni, troppo)
    assert len(errori) == 1
    assert "351,00" in errori[0] and "250,00" in errori[0]


# --- 10. Lo stesso prodotto scritto in modo diverso -----------------------


def test_stesso_prodotto_ignorando_maiuscole_e_spazi_doppi():
    assert c.normalizza_nome("coinbase  5x long") == c.normalizza_nome("Coinbase 5x long")

    diario = Diario()
    diario.versa(date(2026, 10, 1), 250.0)
    diario.compra(date(2026, 10, 5), "Coinbase 5x long", 5, 3.50)
    diario.compra(date(2026, 10, 9), "coinbase  5x long", 4, 3.20)
    diario.vendi(date(2026, 10, 15), "COINBASE 5X LONG", 4, 4.00)

    stato = diario.stato()
    assert len(stato.posizioni) == 1
    posizione = stato.posizione("coinbase 5x long")
    assert posizione.quote == 5
    assert posizione.pmc == pytest.approx(3.366666, abs=1e-5)
    # Il nome resta quello scritto quando la posizione e' stata aperta.
    assert posizione.prodotto == "Coinbase 5x long"
    assert stato.righe[-1].lordo == 0.64


# --- 11. Correggere o cancellare una riga ricalcola tutto il resto --------


def test_eliminare_un_versamento_doppio(coinbase):
    doppio = coinbase.versa(date(2026, 10, 1), 250.0)
    con_doppio = coinbase.stato()
    assert con_doppio.capitale_versato == 500.00
    assert con_doppio.patrimonio == 501.99

    senza = c.ricalcola(coinbase.senza(doppio), oggi=date(2026, 12, 31))
    assert senza.capitale_versato == 250.00
    assert senza.liquidita == 251.99
    assert senza.patrimonio == 251.99
    assert senza.netto_totale == 1.99


def test_correggere_il_prezzo_di_un_acquisto_rifa_pmc_e_vendite(coinbase):
    secondo_acquisto = coinbase.operazioni[2]
    corrette = coinbase.con_modifica(secondo_acquisto, prezzo=3.00)
    stato = c.ricalcola(corrette, oggi=date(2026, 12, 31))

    # PMC = (5 x 3,50 + 4 x 3,00) / 9 = 3,2778
    prima, seconda = stato.righe[3], stato.righe[4]
    assert prima.lordo == 1.00
    assert prima.tasse == 0.26
    assert prima.netto == 0.74
    assert seconda.lordo == 2.50
    assert seconda.tasse == 0.65
    assert seconda.netto == 1.85

    assert stato.lordo_totale == 3.50
    assert stato.tasse_totali == 0.91
    assert stato.netto_totale == 2.59
    assert stato.liquidita == 252.59
    assert stato.patrimonio == 252.59


def test_eliminare_una_vendita_in_mezzo_lascia_aperta_la_posizione(coinbase):
    prima_vendita = coinbase.operazioni[3]
    stato = c.ricalcola(coinbase.senza(prima_vendita), oggi=date(2026, 12, 31))

    vendita = stato.righe[-1]
    assert vendita.lordo == 2.06
    assert vendita.tasse == 0.54
    assert vendita.netto == 1.52
    assert vendita.quote_restanti == 4
    assert vendita.chiude_posizione is False

    posizione = stato.posizione(COINBASE)
    assert posizione.quote == 4
    assert posizione.pmc == pytest.approx(3.366666, abs=1e-5)
    assert posizione.commissioni_acquisto_residue == 0.89
    assert stato.trade_chiusi == []
    assert stato.netto_totale == 1.52
    assert stato.patrimonio == 251.52


# --- Il riepilogo prima di Salva e' lo stesso conto del ricalcolo ---------


def test_anteprima_di_una_vendita_coincide_col_ricalcolo(coinbase):
    operazioni = coinbase.operazioni[:3]
    vendita = Operazione(
        id=c.prossimo_id(operazioni),
        data=date(2026, 10, 15),
        tipo=c.VENDITA,
        prodotto=COINBASE,
        quote=4,
        prezzo=4.00,
        commissione=1.0,
    )
    riga, dopo = c.anteprima(operazioni, vendita)
    assert (riga.lordo, riga.tasse, riga.netto) == (0.64, 0.17, 0.47)
    assert riga.quote_restanti == 5
    assert dopo.liquidita == 232.53
    assert riga.errore == ""


def test_anteprima_di_un_acquisto_mostra_quote_e_pmc_nuovi(coinbase):
    operazioni = coinbase.operazioni[:2]
    acquisto = Operazione(
        id=c.prossimo_id(operazioni),
        data=date(2026, 10, 9),
        tipo=c.ACQUISTO,
        prodotto=COINBASE,
        quote=4,
        prezzo=3.20,
        commissione=1.0,
    )
    riga, dopo = c.anteprima(operazioni, acquisto)
    assert riga.quote_dopo == 9
    assert c.arrotonda(riga.pmc_dopo) == 3.37
    assert riga.costo == 13.80
    assert dopo.liquidita == 217.70


# --- Dettagli di contorno -------------------------------------------------


def test_arrotondamento_a_meta_centesimo_si_allontana_da_zero():
    assert c.arrotonda(0.125) == 0.13
    assert c.arrotonda(0.1664) == 0.17
    assert c.arrotonda(0.5356) == 0.54
    assert c.arrotonda(-0.125) == -0.13  # un gain e una loss uguali, uguale arrotondamento


def test_formati_italiani():
    assert c.euro(1234.5) == "1.234,50 €"
    assert c.euro(0.64, segno=True) == "+0,64 €"
    assert c.euro(-1.5, segno=True) == "-1,50 €"
    assert c.quote_testo(9) == "9"
    assert c.quote_testo(9.5) == "9,5"
    assert c.data_testo(date(2026, 10, 5)) == "05/10/2026"


def test_numeri_scritti_con_la_virgola():
    assert c.leggi_numero("3,50") == 3.50
    assert c.leggi_numero("3.50") == 3.50
    assert c.leggi_numero("1.234,56") == 1234.56
    assert c.leggi_numero("3,20 €") == 3.20
    assert c.leggi_numero(" 4 ") == 4.0
    assert c.leggi_numero("") is None
    assert c.leggi_numero("   ") is None
    assert c.leggi_numero("tre euro") is None
    assert c.leggi_numero(None) is None


def test_il_versamento_non_tocca_il_risultato(coinbase):
    coinbase.versa(date(2026, 10, 21), 250.0)
    stato = coinbase.stato()
    assert stato.capitale_versato == 500.00
    assert stato.netto_totale == 1.99
    assert stato.lordo_totale == 2.70
    assert stato.patrimonio == 501.99
    assert stato.liquidita == 501.99


def test_la_serie_dei_grafici_parte_da_zero(coinbase):
    stato = coinbase.stato()
    assert stato.serie[0].netto == 0.0
    assert stato.serie[0].capitale == 0.0
    assert stato.serie[0].data == date(2026, 10, 1)
    assert [punto.capitale for punto in stato.serie][1:] == [250.0] * 5
    assert stato.serie[-1].netto == 1.99
    assert stato.serie[-1].patrimonio == 251.99


def test_le_operazioni_fuori_ordine_vengono_messe_in_data(coinbase):
    """Segnare un'operazione vecchia la rimette al suo posto nel tempo."""
    fuori_ordine = list(reversed(coinbase.operazioni))
    stato = c.ricalcola(fuori_ordine, oggi=date(2026, 12, 31))
    assert [riga.tipo for riga in stato.righe] == [
        c.VERSAMENTO,
        c.ACQUISTO,
        c.ACQUISTO,
        c.VENDITA,
        c.VENDITA,
    ]
    assert stato.patrimonio == 251.99


def test_il_progresso_verso_i_5000(coinbase):
    stato = coinbase.stato()
    assert stato.progresso == pytest.approx(251.99 / 5000)
