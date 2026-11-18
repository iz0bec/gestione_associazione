# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Aiuti per i test dell'API: una controparte finta con chiavi proprie che firma
# *              le richieste come farebbe un adattatore esterno scritto sul contratto.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import secrets
import time
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from apps.api import chiavi
from apps.api import firma as f


def _pubblica(privata):
    return f.b64url(
        privata.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )


class Controparte:
    """Controparte simulata (altra installazione o integrazione)."""

    def __init__(self, nome="Controparte di prova"):
        self.uuid = uuid.uuid4()
        self.nome = nome
        self.firma = Ed25519PrivateKey.generate()
        self.cifratura = X25519PrivateKey.generate()
        sig = {"kty": "OKP", "crv": "Ed25519", "x": _pubblica(self.firma), "use": "sig"}
        enc = {"kty": "OKP", "crv": "X25519", "x": _pubblica(self.cifratura), "use": "enc"}
        for jwk in (sig, enc):
            jwk["kid"] = chiavi.thumbprint(jwk)
        self.kid = sig["kid"]
        self.jwks = {"keys": [sig, enc]}

    def intestazioni(self, metodo, percorso, corpo=b"", *, destinatario=None, adesso=None,
                     nonce=None, extra=None, componenti=None,
                     tipo="application/json"):  # fmt: skip
        destinatario = destinatario or str(chiavi.istanza().uuid)
        intestazioni = {"Destinatario-Istanza": str(destinatario), **(extra or {})}
        if corpo:
            intestazioni["Content-Type"] = tipo
            intestazioni["Content-Digest"] = f.content_digest(corpo)
        percorso_solo, _, query = percorso.partition("?")
        msg = f.Messaggio(
            intestazioni={k.lower(): v for k, v in intestazioni.items()},
            metodo=metodo, percorso=percorso_solo, query=query,
        )  # fmt: skip
        ingresso, valore = f.firma(
            msg,
            componenti or f.componenti_richiesta(bool(corpo)),
            f.parametri_firma(self.kid, adesso or time.time(), nonce or secrets.token_urlsafe(18)),
            self.firma,
        )
        intestazioni["Signature-Input"] = ingresso
        intestazioni["Signature"] = valore
        return intestazioni

    def chiama(self, client, metodo, percorso, dati=None, *, corpo=None, **opzioni):
        if corpo is None:
            corpo = b"" if dati is None else json.dumps(dati).encode()
        alterato = opzioni.pop("corpo_inviato", None)
        intestazioni = self.intestazioni(metodo, percorso, corpo, **opzioni)
        if alterato is not None:
            corpo = alterato
        tipo = intestazioni.get("Content-Type", "application/json")
        return client.generic(metodo, percorso, data=corpo, content_type=tipo, headers=intestazioni)

    def cifrato(self, client, metodo, percorso, dati, **opzioni):
        """Richiesta con il corpo cifrato (JWE) per la chiave X25519 dell'istanza."""
        from apps.api import jwe

        enc = next(k for k in chiavi.jwks()["keys"] if k["use"] == "enc" and "exp" not in k)
        corpo = jwe.cifra(dati, enc).encode()
        return self.chiama(client, metodo, percorso, corpo=corpo, tipo=jwe.TIPO, **opzioni)

    def decifra(self, risposta):
        from apps.api import jwe

        assert risposta["Content-Type"] == jwe.TIPO, risposta.content
        return jwe.decifra_json(risposta.content.decode(), lambda kid: self.cifratura)

    def richiesta_abbinamento(self, tipo="integrazione"):
        return {"istanza": str(self.uuid), "nome": self.nome, "tipo": tipo, "jwks": self.jwks}


def verifica_risposta(risposta, jwks, msg_richiesta=None):
    """Verifica la firma di una risposta del test client (come farebbe la controparte)."""
    intestazioni = {k.lower(): v for k, v in risposta.headers.items()}
    if not f.verifica_digest(intestazioni.get("content-digest", ""), risposta.content):
        raise AssertionError("digest della risposta errato")
    chiavi_firma = {k["kid"]: k for k in jwks["keys"] if k["use"] == "sig"}
    msg = f.Messaggio(
        intestazioni=intestazioni, stato=risposta.status_code, richiesta=msg_richiesta
    )
    return f.verifica(
        msg,
        lambda kid: f.chiave_pubblica(chiavi_firma[kid]["x"]) if kid in chiavi_firma else None,
        richiesti=f.richiesti(f.componenti_risposta(msg_richiesta is not None)),
        adesso=time.time(),
    )


def messaggio(intestazioni, metodo, percorso):
    return f.Messaggio(
        intestazioni={k.lower(): v for k, v in intestazioni.items()}, metodo=metodo,
        percorso=percorso,
    )  # fmt: skip
