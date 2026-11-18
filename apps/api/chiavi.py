# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Identità dell'istanza: UUID, chiavi Ed25519/X25519 (private cifrate con
# *              CHIAVE_CIFRATURA), JWKS pubblica, rotazione, impronte JWK (RFC 7638) e impronta
# *              dell'abbinamento da confermare per una seconda via.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import hashlib
import json
from datetime import timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.cifratura import cifra, decifra

from .firma import b64url, b64url_decodifica
from .models import ChiaveIstanza, Istanza

CURVA = {ChiaveIstanza.Uso.FIRMA: "Ed25519", ChiaveIstanza.Uso.CIFRATURA: "X25519"}
SOVRAPPOSIZIONE_GIORNI = 7


class JwksNonValida(ValueError):
    pass


def istanza() -> Istanza:
    oggetto = Istanza.objects.order_by("pk").first()
    return oggetto or Istanza.objects.create()


def thumbprint(jwk: dict) -> str:
    """Impronta JWK (RFC 7638) di una chiave OKP: SHA-256 dei membri obbligatori, base64url."""
    canonico = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"]}, separators=(",", ":"), sort_keys=True
    )
    return b64url(hashlib.sha256(canonico.encode()).digest())


def _jwk(chiave: ChiaveIstanza) -> dict:
    jwk = {"kty": "OKP", "crv": CURVA[chiave.uso], "x": chiave.pubblica, "kid": chiave.kid,
           "use": chiave.uso}  # fmt: skip
    if chiave.valida_fino:
        jwk["exp"] = int(chiave.valida_fino.timestamp())
    return jwk


def _genera(uso) -> ChiaveIstanza:
    privata = Ed25519PrivateKey.generate() if uso == "sig" else X25519PrivateKey.generate()
    grezza_priv = privata.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    grezza_pub = privata.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    pubblica = b64url(grezza_pub)
    kid = thumbprint({"kty": "OKP", "crv": CURVA[uso], "x": pubblica})
    return ChiaveIstanza.objects.create(
        kid=kid, uso=uso, pubblica=pubblica, privata=cifra(b64url(grezza_priv))
    )


def _attive():
    return ChiaveIstanza.objects.filter(ritirata_il__isnull=True)


def assicura_chiavi():
    """Crea le chiavi mancanti (serve CHIAVE_CIFRATURA). Rieseguibile."""
    with transaction.atomic():
        Istanza.objects.select_for_update().filter(pk=istanza().pk).first()
        for uso in (ChiaveIstanza.Uso.FIRMA, ChiaveIstanza.Uso.CIFRATURA):
            if not _attive().filter(uso=uso).exists():
                _genera(uso)


def chiave_firma():
    """(kid, Ed25519PrivateKey) della chiave di firma in uso."""
    assicura_chiavi()
    chiave = _attive().filter(uso="sig").order_by("-creata_il").first()
    grezza = b64url_decodifica(decifra(chiave.privata))
    return chiave.kid, Ed25519PrivateKey.from_private_bytes(grezza)


def chiavi_firma_valide():
    """[(kid, privata)] delle chiavi di firma: quella in uso, poi quelle ancora nella
    sovrapposizione della rotazione."""
    chiave_firma()  # crea la chiave se manca
    adesso = timezone.now()
    risultato = []
    for c in (
        ChiaveIstanza.objects.filter(uso="sig")
        .exclude(privata="")
        .order_by(F("ritirata_il").desc(nulls_first=True), "-creata_il")
    ):
        if c.ritirata_il is None or (c.valida_fino and c.valida_fino > adesso):
            grezza = b64url_decodifica(decifra(c.privata))
            risultato.append((c.kid, Ed25519PrivateKey.from_private_bytes(grezza)))
    return risultato


def chiave_cifratura(kid=None) -> X25519PrivateKey | None:
    """Privata X25519 in uso (o quella con `kid`, anche ritirata ma ancora valida)."""
    chiavi = ChiaveIstanza.objects.filter(uso="enc").exclude(privata="")
    chiave = (
        chiavi.filter(kid=kid).first() if kid else chiavi.filter(ritirata_il__isnull=True).first()
    )
    if chiave is None:
        return None
    return X25519PrivateKey.from_private_bytes(b64url_decodifica(decifra(chiave.privata)))


def pubblicate():
    adesso = timezone.now()
    return ChiaveIstanza.objects.filter(ritirata_il__isnull=True) | ChiaveIstanza.objects.filter(
        valida_fino__gt=adesso
    )


def jwks() -> dict:
    """JWKS pubblica: chiavi in uso e quelle ritirate ancora nel periodo di sovrapposizione."""
    assicura_chiavi()
    return {"keys": [_jwk(c) for c in pubblicate().order_by("uso", "-creata_il")]}


def ruota(giorni=SOVRAPPOSIZIONE_GIORNI):
    """Nuove chiavi; le precedenti restano valide `giorni` giorni."""
    with transaction.atomic():
        adesso = timezone.now()
        precedenti = list(_attive().select_for_update())
        for chiave in precedenti:
            chiave.ritirata_il = adesso
            chiave.valida_fino = adesso + timedelta(days=giorni)
            chiave.save(update_fields=["ritirata_il", "valida_fino"])
        nuove = [_genera(uso) for uso in ("sig", "enc")]
    return precedenti, nuove


def scarta_scadute():
    """Cancella le private delle chiavi uscite dalla sovrapposizione."""
    return (
        ChiaveIstanza.objects.filter(valida_fino__lte=timezone.now())
        .exclude(privata="")
        .update(privata="")
    )


def valida_jwks(dati) -> dict:
    """Controlla la JWKS di una controparte: chiavi OKP con kid = impronta RFC 7638, almeno una
    Ed25519 per la firma e una X25519 per la cifratura. Restituisce la JWKS ripulita."""
    if not isinstance(dati, dict) or not isinstance(dati.get("keys"), list):
        raise JwksNonValida("La JWKS deve contenere l'elenco keys.")
    if not 2 <= len(dati["keys"]) <= 6:
        raise JwksNonValida("La JWKS deve avere da 2 a 6 chiavi.")
    pulite, kid_visti = [], set()
    for jwk in dati["keys"]:
        if not isinstance(jwk, dict) or jwk.get("kty") != "OKP":
            raise JwksNonValida("Sono ammesse solo chiavi OKP.")
        coppia = (jwk.get("crv"), jwk.get("use"))
        if coppia not in (("Ed25519", "sig"), ("X25519", "enc")):
            raise JwksNonValida("Chiavi ammesse: Ed25519 per sig, X25519 per enc.")
        try:
            if len(b64url_decodifica(jwk.get("x", ""))) != 32:
                raise ValueError
        except ValueError as e:
            raise JwksNonValida("Chiave pubblica non valida.") from e
        kid = thumbprint(jwk)
        if jwk.get("kid") != kid:
            raise JwksNonValida("Il kid di ogni chiave deve essere la sua impronta RFC 7638.")
        if kid in kid_visti:
            raise JwksNonValida("Chiave ripetuta.")
        kid_visti.add(kid)
        pulita = {k: jwk[k] for k in ("kty", "crv", "x", "kid", "use")}
        if isinstance(jwk.get("exp"), int):
            pulita["exp"] = jwk["exp"]
        pulite.append(pulita)
    usi = {k["use"] for k in pulite}
    if usi != {"sig", "enc"}:
        raise JwksNonValida("Servono almeno una chiave di firma e una di cifratura.")
    return {"keys": pulite}


def impronta_abbinamento(jwks_a: dict, jwks_b: dict) -> str:
    """Impronta comune alle due parti (non dipende da chi è «a» o «b»): SHA-256 delle impronte
    delle chiavi in uso di entrambe, ordinate; mostrata come 8 gruppi di 4 cifre esadecimali."""
    impronte = sorted(
        thumbprint(k) for jw in (jwks_a, jwks_b) for k in jw.get("keys", []) if "exp" not in k
    )
    esadecimale = hashlib.sha256("\n".join(impronte).encode()).hexdigest().upper()[:32]
    return " ".join(esadecimale[i : i + 4] for i in range(0, 32, 4))
