# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Veste grafica delle email: testata con logo incorporato (cid:), corpo dal
# *              testo dell'utente (Markdown, indirizzi cliccabili), firma e informativa in
# *              calce. Impostazioni in Sistema -> Aspetto (campi email_* dell'Organizzazione).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import re
from urllib.parse import urlsplit

import markdown as md
from django.core.mail import EmailMultiAlternatives
from django.template.defaultfilters import linebreaksbr
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape, linebreaks

from .models import Organizzazione, testo_leggibile

CID_LOGO = "logo@gestione-associazione"
LATO_LOGO = 128  # pixel del file; mostrato a 64 (schermi ad alta densità)
TRICOLORE = ("#1a8a3c", "#ffffff", "#cc2b2b")
CARATTERI = {
    Organizzazione.CarattereEmail.GRAZIE: "Georgia,'Times New Roman',serif",
    Organizzazione.CarattereEmail.BASTONE: "Arial,Helvetica,sans-serif",
}
CARATTERE_TESTO = "Arial,Helvetica,sans-serif"

# indirizzi web (anche tra < >) ed email nel testo semplice; non quelli già in un link Markdown
_INDIRIZZI = re.compile(
    r"<(?P<url1>https?://[^\s<>]+)>"
    r"|(?<!\]\()(?P<url>https?://[^\s<>\"']*[^\s<>\"'.,;:!?)\]])"
    r"|(?<![\w.+-])(?P<email>[\w.+-]+@[\w-]+(?:\.[\w-]+)+)"
)

# indirizzo spezzato su due righe dopo una barra (testo incollato da un PDF): si ricompone
_URL_SPEZZATO = re.compile(r"(https?://\S+/)[ \t]*\n(?=[\w-]+(?:[./][\w-]+)*\.\w{2,5}\b|[\w-]+/)")
_FINE_FRASE = re.compile(r"([.!?:])[ \t]*\n(?=[^\n])")


class EmailConVeste(EmailMultiAlternatives):
    """Email con l'HTML della veste: il logo viaggia come parte «related» dell'HTML."""

    logo_png = None

    def _add_bodies(self, msg):
        super()._add_bodies(msg)
        html = msg.get_body(("html",)) if self.logo_png else None
        if html is not None:
            html.add_related(
                self.logo_png, "image", "png", cid=f"<{CID_LOGO}>",
                disposition="inline", filename="logo.png",
            )  # fmt: skip
        return msg


def _mescola(colore, altro, quota):
    """Colore a metà strada (quota 0..1 verso `altro`), per i testi attenuati."""
    a = [int(colore[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(altro[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * quota):02x}" for x, y in zip(a, b, strict=True))


def colori(org):
    testata = org.email_colore_testata or org.colore_primario
    accento = org.email_colore_accento or org.colore_primario
    sfondo = org.email_colore_sfondo or "#f1ede6"
    testo_testata = testo_leggibile(testata)
    # sullo sfondo bianco un accento troppo chiaro non si legge: si scurisce
    leggibile = accento
    if testo_leggibile(accento) != "#ffffff":
        leggibile = _mescola(accento, "#000000", 0.45)
    return {
        "testata": testata,
        "testo_testata": testo_testata,
        "sottotitolo": _mescola(testo_testata, testata, 0.25),
        "accento": accento,
        "collegamenti": leggibile,
        "sfondo": sfondo,
        "tenue": _mescola(sfondo, "#000000", 0.45),
        "filetto_tenue": _mescola(sfondo, "#000000", 0.1),
    }


_cache_logo = {}


def logo_png(org):
    """Logo ridotto per le email (PNG); None se non c'è o non va mostrato."""
    if not (org.email_logo and org.logo):
        return None
    chiave = (org.logo.name, org.versione_aspetto)
    if chiave not in _cache_logo:
        from PIL import Image

        try:
            with org.logo.open("rb") as f:
                img = Image.open(f)
                img.load()
        except (OSError, ValueError):
            return None
        img.thumbnail((LATO_LOGO, LATO_LOGO))
        uscita = io.BytesIO()
        img.save(uscita, "PNG", optimize=True)
        _cache_logo.clear()
        _cache_logo[chiave] = uscita.getvalue()
    return _cache_logo[chiave]


def _stile_tag(html, colori_):
    """Gli stili in linea che i programmi di posta richiedono (niente fogli di stile); i titoli
    scendono di un livello (il titolo del messaggio è l'unico h1)."""
    stili = {
        "p": "margin:0 0 14px",
        "ul": "margin:0 0 14px;padding-left:22px",
        "ol": "margin:0 0 14px;padding-left:22px",
        "li": "margin:0 0 4px",
        "h2": "font-size:18px;margin:18px 0 10px",
        "h3": "font-size:16px;margin:16px 0 8px",
        "h4": "font-size:15px;margin:14px 0 6px",
        "a": f"color:{colori_['collegamenti']};word-break:break-word",
    }
    giu = {"h1": "h2", "h2": "h3", "h3": "h4"}

    def sostituisci(m):
        chiusura, tag, resto = m[1], m[2], m[3]
        tag = giu.get(tag, tag)
        if chiusura:
            return f"</{tag}>"
        return f'<{tag} style="{stili[tag]}"{resto}>'

    html = re.sub(r"<(/?)(p|ul|ol|li|h1|h2|h3|a)((?:\s[^>]*)?)>", sostituisci, html)
    filetto = colori_["filetto_tenue"]
    riga = f'<hr style="border:0;border-top:1px solid {filetto};margin:18px 0">'
    return html.replace("<hr />", riga)


def _con_collegamenti(testo, converti):
    """Indirizzi web ed email tolti dal testo, `converti` applicato al testo neutralizzato,
    poi gli indirizzi rimessi come collegamenti."""
    trovati = []

    def segnaposto(m):
        trovati.append(m)
        return f"zqLINK{len(trovati) - 1}qz"

    html = converti(escape(_INDIRIZZI.sub(segnaposto, _URL_SPEZZATO.sub(r"\1", testo or ""))))

    def collegamento(m):
        trovato = trovati[int(m[1])]
        if trovato["email"]:
            return f'<a href="mailto:{escape(trovato["email"])}">{escape(trovato["email"])}</a>'
        url = trovato["url1"] or trovato["url"]
        return f'<a href="{escape(url)}">{escape(url)}</a>'

    return re.sub(r"zqLINK(\d+)qz", collegamento, html)


def testo_html(testo, *, org=None, markdown=True):
    """HTML del testo scritto dall'utente: neutralizzato, poi Markdown (le righe spezzate si
    ricompongono in paragrafi, tranne dopo . ! ? :) o, con markdown=False, a capo conservati;
    indirizzi web ed email diventano collegamenti."""
    org = org or Organizzazione.corrente()

    def converti(composto):
        if not markdown:
            return linebreaks(composto)
        # a fine frase si va a capo (firme, saluti); il resto si ricompone
        return md.markdown(_FINE_FRASE.sub(r"\1  \n", composto), extensions=["sane_lists"])

    return _stile_tag(_con_collegamenti(testo, converti), colori(org))


def testo_piccolo(testo, colore):
    """Avviso e informativa in calce: a capo conservati, collegamenti nel colore del testo."""
    html = _con_collegamenti(testo.strip(), lambda t: linebreaksbr(t, autoescape=False))
    return html.replace("<a href=", f'<a style="color:{colore}" href=')


def righe_firma(org):
    if org.email_firma.strip():
        return [r.strip() for r in org.email_firma.splitlines() if r.strip()]
    righe = []
    luogo = " ".join(x for x in (org.cap, org.comune) if x)
    if org.provincia and luogo:
        luogo += f" ({org.provincia})"
    if indirizzo := ", ".join(x for x in (org.indirizzo, luogo) if x):
        righe.append(indirizzo)
    contatti = [x for x in (org.telefono, org.email) if x]
    if contatti:
        righe.append(" · ".join(contatti))
    if org.sito_web:
        righe.append(org.sito_web)
    return righe


def html(org=None, *, titolo="", corpo_html="", avviso="", sobrio=False, anteprima=False):
    """Pagina HTML completa del messaggio. `sobrio`: spedizioni ufficiali (protocollo), senza
    fascia decorativa né informativa. `anteprima`: logo dal sito invece che incorporato."""
    org = org or Organizzazione.corrente()
    c = colori(org)
    fascia = ()
    if not sobrio and org.email_fascia == Organizzazione.FasciaEmail.TRICOLORE:
        fascia = TRICOLORE
    elif not sobrio and org.email_fascia == Organizzazione.FasciaEmail.COLORE:
        fascia = (c["accento"],)
    logo = None
    if logo_png(org):
        logo = f"{reverse('logo')}?v={org.versione_aspetto}" if anteprima else f"cid:{CID_LOGO}"
    firma = righe_firma(org)
    collegamenti_firma = []
    for riga in firma:
        if riga.startswith(("http://", "https://")):
            collegamenti_firma.append({"url": riga, "testo": urlsplit(riga).netloc or riga})
        else:
            collegamenti_firma.append({"testo": riga})
    return render_to_string(
        "email/veste.html",
        {
            "org": org,
            "c": c,
            "fascia": fascia,
            "larghezza_fascia": round(100 / len(fascia)) if fascia else 0,
            "titoli": CARATTERI.get(org.email_carattere, CARATTERI["grazie"]),
            "testo": CARATTERE_TESTO,
            "logo": logo,
            "nome": org.email_titolo or org.denominazione,
            "sottotitolo": org.email_sottotitolo,
            "titolo": titolo,
            "corpo": corpo_html,
            "firma": collegamenti_firma,
            "avviso": testo_piccolo(avviso, c["tenue"]),
            "informativa": "" if sobrio else testo_piccolo(org.email_informativa, c["tenue"]),
        },
    )


def veste(msg, org=None, *, testo=None, titolo=None, avviso="", sobrio=False, markdown=True):
    """Restituisce una copia di `msg` (EmailMessage) con l'HTML della veste e il logo.
    `testo`: quello da impaginare (predefinito: il corpo); `titolo`: predefinito l'oggetto."""
    org = org or Organizzazione.corrente()
    nuova = EmailConVeste(
        subject=msg.subject,
        body=msg.body,
        from_email=msg.from_email,
        to=msg.to,
        cc=msg.cc,
        bcc=msg.bcc,
        reply_to=msg.reply_to,
        headers=msg.extra_headers,
        attachments=msg.attachments,
    )
    corpo = testo_html(msg.body if testo is None else testo, org=org, markdown=markdown)
    nuova.attach_alternative(
        html(org, titolo=msg.subject if titolo is None else titolo, corpo_html=corpo,
             avviso=avviso, sobrio=sobrio),
        "text/html",
    )  # fmt: skip
    nuova.logo_png = logo_png(org)
    return nuova
