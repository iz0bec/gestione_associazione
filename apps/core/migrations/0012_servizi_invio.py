# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Servizi di invio (SMTP); il server del file .env diventa il servizio generale.
# *              Rieseguibile: non crea nulla se esiste già un servizio.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************
from django.db import migrations, models


def servizio_da_env(apps, schema_editor):
    """Il server SMTP del .env (se configurato davvero) diventa il «server generale»."""
    from email.utils import parseaddr

    from django.conf import settings

    from apps.core.cifratura import cifra, cifratura_disponibile

    servizi = apps.get_model("core", "ServizioInvio")
    mailer = settings.MAILERS.get("default", {})
    if servizi.objects.exists() or not mailer.get("BACKEND", "").endswith(
        ("invio.Backend", "smtp.EmailBackend")
    ):
        return
    opzioni = mailer.get("OPTIONS", {})
    host, password = opzioni.get("host", ""), opzioni.get("password", "")
    if host in ("", "localhost", "127.0.0.1") or not password or not cifratura_disponibile():
        return
    utente = opzioni.get("username", "")
    nome, indirizzo = parseaddr(settings.DEFAULT_FROM_EMAIL)
    if "@" not in indirizzo:
        indirizzo = utente
    if "@" not in indirizzo:
        return
    servizi.objects.create(
        nome="Email (server generale)",
        tipo="email",
        indirizzo=indirizzo,
        nome_mittente=nome,
        server=host,
        porta=opzioni.get("port") or 465,
        ssl=bool(opzioni.get("use_ssl")),
        utente="" if utente == indirizzo else utente,
        password_cifrata=cifra(password),
        generale=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_firme_e_timbri_generici"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServizioInvio",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "nome",
                    models.CharField(help_text="Es. «PEC della federazione».", max_length=100),
                ),
                (
                    "tipo",
                    models.CharField(
                        choices=[("email", "Email"), ("pec", "PEC")], default="email", max_length=5
                    ),
                ),
                (
                    "indirizzo",
                    models.EmailField(max_length=254, verbose_name="indirizzo del mittente"),
                ),
                (
                    "nome_mittente",
                    models.CharField(
                        blank=True,
                        help_text="Mostrato a chi riceve. Vuoto: la denominazione dell'organizzazione.",
                        max_length=200,
                        verbose_name="nome del mittente",
                    ),
                ),
                (
                    "server",
                    models.CharField(
                        help_text="Es. smtps.pec.aruba.it",
                        max_length=200,
                        verbose_name="server SMTP",
                    ),
                ),
                ("porta", models.PositiveIntegerField(default=465)),
                (
                    "ssl",
                    models.BooleanField(
                        default=True,
                        help_text="Porta 465: SSL; porta 587: togliere la spunta (si usa STARTTLS).",
                        verbose_name="SSL implicito",
                    ),
                ),
                (
                    "utente",
                    models.CharField(
                        blank=True,
                        help_text="Vuoto: l'indirizzo del mittente.",
                        max_length=200,
                        verbose_name="nome utente",
                    ),
                ),
                ("password_cifrata", models.TextField(blank=True, editable=False)),
                (
                    "generale",
                    models.BooleanField(
                        default=False,
                        help_text="Spedisce le comunicazioni, le email dell'accesso (es. recupero password) e i protocolli per email. Uno solo.",
                        verbose_name="server generale",
                    ),
                ),
                ("attivo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "servizio di invio",
                "verbose_name_plural": "servizi di invio",
                "ordering": ["-generale", "tipo", "nome"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("generale", True)),
                        fields=("generale",),
                        name="un_solo_servizio_generale",
                    )
                ],
            },
        ),
        migrations.RunPython(servizio_da_env, migrations.RunPython.noop),
    ]
