# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Ambiente dimostrativo (DEMO=true nel .env): azzeramento del database e dei file,
# *              dati di fantasia (quelli del manuale), logo generato, un utente per ruolo con la
# *              password pubblica e l'amministratore con quella privata. Rifiuta di funzionare
# *              senza DEMO=true: cancella tutto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import io
import runpy
import secrets
import shutil
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone

DATI = Path(settings.BASE_DIR) / "scripts" / "manuale" / "dati_demo.py"
DESCRIZIONE_AZZERAMENTO = "Ambiente dimostrativo azzerato"

# utenti pubblici: (nome utente, ruolo, cosa può provare)
ACCOUNT = [
    ("presidente", "Presidente", "soci, domande, organi sociali, firme"),
    ("segretario", "Segretario", "soci, protocollo, comunicazioni, verbali"),
    ("tesoriere", "Tesoriere", "quote, prima nota, rendiconto"),
    ("protocollo", "Addetto protocollo", "registro di protocollo e posta"),
    ("sezione", "Presidente di sezione", "soci della sola sezione di Valleverde"),
    ("consigliere", "Consigliere", "consultazione"),
    ("revisore", "Revisore", "controllo dei conti"),
]
ADMIN = "admin"


class DemoNonAttiva(Exception):
    pass


def attiva():
    return bool(getattr(settings, "DEMO", False))


def password_pubblica():
    return settings.DEMO_PASSWORD


def _svuota_file():
    radice = Path(settings.MEDIA_ROOT)
    if radice.is_dir():
        for voce in radice.iterdir():
            if voce.is_dir():
                shutil.rmtree(voce)
            else:
                voce.unlink()


def logo_generato(colore="#0e2525", accento="#a0876e"):
    """Emblema di fantasia: due cerchi e le iniziali, senza marchi reali."""
    from PIL import Image, ImageDraw, ImageFont

    lato = 512
    img = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, lato - 8, lato - 8), fill=colore)
    d.ellipse((40, 40, lato - 40, lato - 40), outline=accento, width=10)
    d.ellipse((70, 70, lato - 70, lato - 70), outline="#f1ede6", width=3)
    font = ImageFont.load_default(size=190)
    d.text((lato / 2, lato / 2 - 6), "AE", fill="#f1ede6", font=font, anchor="mm")
    uscita = io.BytesIO()
    img.save(uscita, "PNG")
    return uscita.getvalue()


def _utenti(admin_password):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from apps.accounts.models import PoliticaRuolo
    from apps.soci.models import Sezione

    U = get_user_model()
    PoliticaRuolo.objects.update(mfa_obbligatoria=False)
    # l'utente «demo» dei dati del manuale diventa l'amministratore privato
    admin = U.objects.get(username="demo")
    admin.username = ADMIN
    admin.set_password(admin_password)
    admin.puo_cambiare_password = True
    admin.save()
    valleverde = Sezione.objects.filter(nome="Valleverde").first()
    for nome, ruolo, _ in ACCOUNT:
        u = U.objects.create_user(
            nome, email=f"{nome}@esempio.invalid", password=password_pubblica(),
            first_name=ruolo, last_name="(dimostrativo)",
        )  # fmt: skip
        u.puo_cambiare_password = False  # nessun visitatore chiude fuori gli altri
        u.save(update_fields=["puo_cambiare_password"])
        u.groups.add(Group.objects.get(name=ruolo))
        if nome == "sezione" and valleverde:
            u.sezioni.add(valleverde)


def _organizzazione():
    from apps.core.models import Organizzazione

    org = Organizzazione.corrente()
    org.logo.save("logo.png", ContentFile(logo_generato()), save=False)
    org.colore_primario = "#0e2525"
    org.stile_menu = Organizzazione.StileMenu.COLORATO
    org.email_titolo, org.email_sottotitolo = "Associazione di Esempio", "Federazione Provinciale"
    org.email_fascia = Organizzazione.FasciaEmail.TRICOLORE
    org.email_colore_accento = "#a0876e"
    # niente messaggi veri verso l'esterno e niente caselle da leggere
    org.invio_email = False
    org.ricezione_posta = False
    org.iscrizioni_online = True
    org.save()


def azzera(admin_password=None, *, stdout=None):
    """Cancella database e file, ricrea tutto con i dati di fantasia. Restituisce la password
    dell'amministratore (generata se non indicata né presente in DEMO_ADMIN_PASSWORD)."""
    if not attiva():
        raise DemoNonAttiva("Rifiutato: l'azzeramento funziona solo con DEMO=true nel .env.")
    from apps.core import backup

    admin_password = admin_password or settings.DEMO_ADMIN_PASSWORD or secrets.token_urlsafe(12)
    with transaction.atomic():
        backup.svuota_database()
    _svuota_file()
    call_command("migrate", interactive=False, verbosity=0)
    connection.close()  # le tabelle sono nuove: nessuna cache di connessione vecchia
    runpy.run_path(str(DATI), run_name="__demo__")
    _utenti(admin_password)
    _organizzazione()
    from apps.core.audit import Azione, registra

    registra(Azione.MODIFICA, None, descrizione=DESCRIZIONE_AZZERAMENTO)
    if stdout is not None:
        stdout.write(f"Ambiente dimostrativo azzerato il {timezone.localtime():%d/%m/%Y %H:%M}.")
    return admin_password


def azzeramento_dovuto(adesso=None):
    """Il 1° del mese, se non è già stato azzerato da quel giorno (per il pianificatore)."""
    if not attiva():
        return False
    from apps.core.models import EventoAudit

    adesso = adesso or timezone.localtime()
    if adesso.day != 1:
        return False
    inizio = adesso.replace(hour=0, minute=0, second=0, microsecond=0)
    return not EventoAudit.objects.filter(
        oggetto_descrizione=DESCRIZIONE_AZZERAMENTO, momento__gte=inizio
    ).exists()
