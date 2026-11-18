# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Messaggi del modulo contatti ricevuti via API: diventano un messaggio della
# *              posta da protocollare (casella interna), con lo stesso percorso della posta vera.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import uuid
from email.message import EmailMessage
from email.utils import format_datetime, formataddr

from django.utils import timezone

from apps.core.audit import Azione, registra
from apps.core.models import Organizzazione

from . import chiavi

NOME_CASELLA = "Modulo contatti (API)"


def casella_interna():
    from apps.protocollo.models import CasellaPosta

    casella = CasellaPosta.tutte.filter(interna=True).first()
    if casella is None:
        casella = CasellaPosta.tutte.create(
            nome=NOME_CASELLA, interna=True, server="", utente="", attiva=False
        )
    return casella


def ricevi(cliente, *, nome, email, testo, oggetto="", telefono="", riferimento_esterno=""):
    from apps.protocollo import posta

    org = Organizzazione.corrente()
    messaggio = EmailMessage()
    messaggio["From"] = formataddr((nome, email))
    messaggio["To"] = org.email or "segreteria@localhost"
    messaggio["Subject"] = oggetto or f"Messaggio dal modulo contatti di {cliente}"
    messaggio["Date"] = format_datetime(timezone.now())
    messaggio["Message-ID"] = f"<api-{uuid.uuid4()}@{chiavi.istanza().uuid}>"
    messaggio["X-Gestione-Controparte"] = cliente.nome
    righe = [testo, "", "--", f"Inviato dal modulo contatti di: {cliente}"]
    if telefono:
        righe.append(f"Telefono: {telefono}")
    if riferimento_esterno:
        righe.append(f"Riferimento: {riferimento_esterno}")
    messaggio.set_content("\n".join(righe))
    ricevuto = posta.salva_messaggio(casella_interna(), messaggio.as_bytes())
    registra(Azione.CREAZIONE, ricevuto, descrizione=f"Messaggio dal modulo contatti di {cliente}",
             controparte=cliente.nome)  # fmt: skip
    return ricevuto
