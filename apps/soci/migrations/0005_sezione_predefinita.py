# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Crea la sezione predefinita e vi assegna soci e lotti di tessere esistenti;
# *              crea i listini degli anni già tesserati dalle quote e dai costi registrati.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from django.db import migrations


def avanti(apps, schema_editor):
    Sezione = apps.get_model("soci", "Sezione")
    Organizzazione = apps.get_model("core", "Organizzazione")
    org = Organizzazione.objects.filter(pk=1).first()
    nome = (org.denominazione_breve or org.denominazione) if org else ""
    if not nome or nome == "Associazione":
        nome = "Sezione principale"
    sezione = Sezione.objects.order_by("pk").first() or Sezione.objects.create(
        codice="001", nome=nome, comune=org.comune if org else "",
        provincia=org.provincia if org else "",
    )  # fmt: skip
    apps.get_model("soci", "Socio").objects.filter(sezione__isnull=True).update(sezione=sezione)
    Lotto = apps.get_model("soci", "LottoTessere")
    Lotto.objects.filter(sezione__isnull=True).update(sezione=sezione)

    # listini degli anni già gestiti: costo dall'ultimo lotto, quote dalle tipologie
    Listino = apps.get_model("soci", "ListinoTessere")
    Quota = apps.get_model("soci", "QuotaListino")
    Tipologia = apps.get_model("soci", "TipologiaSocio")
    Tessera = apps.get_model("soci", "Tessera")
    anni = set(Tessera.objects.values_list("anno", flat=True)) | set(
        Lotto.objects.values_list("anno", flat=True)
    )
    for anno in sorted(anni):
        if Listino.objects.filter(anno=anno).exists():
            continue
        lotto = Lotto.objects.filter(anno=anno).order_by("-data_acquisizione").first()
        listino = Listino.objects.create(anno=anno, costo_acquisto=lotto.costo_unitario if lotto else 0)
        for t in Tipologia.objects.all():
            Quota.objects.create(listino=listino, tipologia=t, importo=t.quota_annua)


class Migration(migrations.Migration):
    dependencies = [
        ("soci", "0004_sezioni_e_listino"),
        ("core", "0002_iscrizioni_online"),
    ]

    operations = [migrations.RunPython(avanti, migrations.RunPython.noop)]
