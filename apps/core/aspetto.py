# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Personalizzazione dell'interfaccia: logo (ripulito, PNG) e foglio di stile
# *              con il colore dell'organizzazione, servito come file (compatibile con la CSP);
# *              veste grafica delle email (anteprima e messaggio di prova).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.http import require_GET

from .audit import Azione, campi_modificati, registra
from .immagini import ripulisci, risposta_immagine
from .models import Organizzazione

LATO_LOGO = 512


@transaction.atomic
def salva_aspetto(form, utente, *, logo=None, togli_logo=False):
    dettagli = campi_modificati(form)
    org = form.save(commit=False)
    if logo:
        nuovo = ripulisci(logo, lato=LATO_LOGO, formato="PNG")
        if org.logo:
            org.logo.delete(save=False)
        org.logo.save("logo.png", nuovo, save=False)
    elif togli_logo and org.logo:
        org.logo.delete(save=False)
    org.save()
    if dettagli.get("campi") or logo or togli_logo:
        registra(Azione.MODIFICA, org, utente=utente, logo=bool(logo) or None, **dettagli)
    return org


class ProvaNonInviata(Exception):
    pass


@transaction.atomic
def salva_aspetto_email(form, utente):
    dettagli = campi_modificati(form)
    org = form.save()
    if dettagli.get("campi"):
        registra(Azione.MODIFICA, org, utente=utente, descrizione="Veste delle email", **dettagli)
    return org


TITOLO_ESEMPIO = "Convocazione dell'assemblea dei soci"
TESTO_ESEMPIO = """Gentile Mario Rossi,

è convocata l'**assemblea ordinaria dei soci** presso la sede, con il seguente ordine del giorno:

1. approvazione del rendiconto;
2. rinnovo delle cariche sociali;
3. varie ed eventuali.

Il regolamento è consultabile su https://www.example.org/regolamento e per informazioni si può
scrivere a segreteria@example.org.

Cordiali saluti.
Il Presidente"""
AVVISO_ESEMPIO = "Comunicazione inviata per lo svolgimento della vita associativa."


def anteprima_email(org=None):
    from . import veste_email

    org = org or Organizzazione.corrente()
    return veste_email.html(
        org,
        titolo=TITOLO_ESEMPIO,
        corpo_html=veste_email.testo_html(TESTO_ESEMPIO, org=org),
        avviso=AVVISO_ESEMPIO,
        anteprima=True,
    )


def invia_prova(utente):
    """Messaggio di esempio all'email dell'utente, dal server generale (Servizi di posta)."""
    from django.core.mail import EmailMessage

    from . import veste_email

    org = Organizzazione.corrente()
    if not utente.email:
        raise ProvaNonInviata("Il tuo utente non ha un indirizzo email.")
    if not org.invio_email:
        raise ProvaNonInviata("L'invio dei messaggi è spento (Sistema → Servizi di posta).")
    email = EmailMessage(
        subject=f"Prova della veste delle email - {org.denominazione}",
        body=f"{TESTO_ESEMPIO}\n\n-- \n{org.denominazione}\n{AVVISO_ESEMPIO}",
        to=[utente.email],
    )
    veste_email.veste(email, org, testo=TESTO_ESEMPIO, titolo=TITOLO_ESEMPIO,
                      avviso=AVVISO_ESEMPIO).send()  # fmt: skip
    registra(Azione.CREAZIONE, org, utente=utente, descrizione="Email di prova della veste",
             a=utente.email)  # fmt: skip
    return utente.email


def foglio_di_stile(org):
    colore, testo, rgb = org.colore_primario, org.colore_testo_primario, org.colore_rgb
    regole = f"""/* aspetto di {org.nome_breve}: generato dall'applicazione */
:root, [data-bs-theme] {{
  --tblr-primary: {colore};
  --tblr-primary-rgb: {rgb};
  --tblr-primary-fg: {testo};
  --ga-colore-marchio: {colore};
  --ga-colore-marchio-testo: {testo};
}}
"""
    if org.stile_menu == Organizzazione.StileMenu.COLORATO:
        regole += f""".navbar-vertical.menu-colorato {{
  background: {colore} !important;
  --tblr-navbar-bg: {colore};
  --tblr-navbar-color: {testo};
  --tblr-navbar-active-color: {testo};
  --tblr-navbar-hover-color: {testo};
  color: {testo};
}}
.navbar-vertical.menu-colorato .marchio {{ background: rgba(255, 255, 255, .2); }}
"""
    return regole


@require_GET
def aspetto_css(request):
    risposta = HttpResponse(foglio_di_stile(Organizzazione.corrente()), content_type="text/css")
    # l'indirizzo contiene la versione (?v=...): cambia a ogni modifica dell'aspetto
    risposta["Cache-Control"] = (
        "public, max-age=31536000, immutable" if "v" in request.GET else "no-cache"
    )
    return risposta


@require_GET
def logo(request):
    risposta = risposta_immagine(Organizzazione.corrente().logo, privata=False)
    if "v" in request.GET:
        risposta["Cache-Control"] = "public, max-age=31536000, immutable"
    return risposta
