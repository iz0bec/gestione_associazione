# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Utenti da riga di comando: elenco e reimpostazione della password alla
# *              predefinita (della carica, o iniziale per gli amministratori), con l'email di
# *              notifica come ultimo passo (inviata subito, in bozza o non preparata).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts import servizi
from apps.accounts.models import Utente


class Command(BaseCommand):
    help = (
        "Elenca gli utenti; con --reimposta NOME riporta la password alla predefinita e, come "
        "ultimo passo, chiede se inviare subito l'email di notifica (--invia / --senza-email)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reimposta", metavar="NOME", help="Utente a cui reimpostare la password"
        )
        parser.add_argument("--password", help="Password da usare invece della predefinita")
        parser.add_argument(
            "--obbligo-cambio", action="store_true", help="Obbliga a cambiarla al primo accesso"
        )
        email = parser.add_mutually_exclusive_group()
        email.add_argument(
            "--invia", action="store_true", help="Invia subito l'email, senza domanda"
        )
        email.add_argument("--senza-email", action="store_true", help="Non preparare l'email")
        parser.add_argument("--tutti", action="store_true", help="Elenco: anche i non attivi")

    def handle(self, *args, **o):
        if o["reimposta"]:
            return self._reimposta(o)
        return self._elenco(o["tutti"])

    def _elenco(self, tutti):
        from allauth.mfa.models import Authenticator

        predefinite = servizi.password_predefinite()
        utenti = Utente.objects.select_related("soggetto").prefetch_related("groups")
        if not tutti:
            utenti = utenti.filter(is_active=True)
        con_mfa = set(
            Authenticator.objects.filter(type__in=servizi.FATTORI_FORTI).values_list(
                "user_id", flat=True
            )
        )
        righe = []
        for u in utenti.order_by("username"):
            categoria = servizi.categoria_utente(u)
            email = "segnaposto" if u.email.endswith(servizi.EMAIL_SEGNAPOSTO) else (u.email or "-")
            ultimo = (
                timezone.localtime(u.last_login).strftime("%d/%m/%Y") if u.last_login else "mai"
            )
            righe.append(
                (
                    u.username,
                    (u.get_full_name() or "-")[:28],
                    ", ".join(g.name for g in u.groups.all())[:40] or "-",
                    "sì" if u.is_active else "no",
                    "sì" if u.pk in con_mfa else "no",
                    ultimo,
                    email[:34],
                    (categoria or "-") + (" ✓" if categoria in predefinite else ""),
                )
            )
        intestazione = (
            "UTENTE",
            "PERSONA",
            "RUOLI",
            "ATTIVO",
            "2FA",
            "ULTIMO",
            "EMAIL",
            "PREDEFINITA",
        )
        larghezze = [max(len(str(r[i])) for r in [intestazione, *righe]) for i in range(8)]
        for r in [intestazione, *righe]:
            self.stdout.write("  ".join(str(v).ljust(larghezze[i]) for i, v in enumerate(r)))
        file = settings.PASSWORD_PREDEFINITE or "file non configurato"
        self.stdout.write(f"\n{len(righe)} utenti. «✓»: password predefinita disponibile ({file}).")

    def _reimposta(self, o):
        try:
            utente = Utente.objects.select_related("soggetto").get(username__iexact=o["reimposta"])
        except Utente.DoesNotExist as e:
            raise CommandError(f"Utente «{o['reimposta']}» inesistente.") from e
        try:
            password, categoria, origine = servizi.reimposta_predefinita(
                utente, password=o["password"], obbligo_cambio=o["obbligo_cambio"]
            )
        except servizi.ValidationError as e:
            raise CommandError(" ".join(e.messages)) from e
        spiegazione = {
            "predefinita": f"predefinita della categoria «{categoria}»",
            "indicata": "indicata con --password",
            "generata": f"generata (nessuna predefinita per «{categoria or '-'}»)",
        }[origine]
        self.stdout.write(
            self.style.SUCCESS(f"Password di «{utente.username}» reimpostata: {spiegazione}.")
        )
        if origine == "generata":
            self.stdout.write(f"Nuova password (mostrata solo ora): {password}")
        # ultimo passo: l'email di notifica
        if o["senza_email"]:
            return
        if not utente.is_active:
            self.stdout.write("Utente non attivo: nessuna email preparata.")
            return
        invia = o["invia"]
        if not invia and sys.stdin.isatty():
            risposta = input("Inviare ora l'email con le credenziali? [s/N] ").strip().lower()
            invia = risposta in ("s", "si", "sì", "y", "yes")
        indirizzo = settings.URL_PUBBLICO or "(indirizzo del gestionale)"
        _, esito = servizi.notifica_credenziali(utente, password, indirizzo, invia=invia)
        self.stdout.write(f"Email: {esito}.")
