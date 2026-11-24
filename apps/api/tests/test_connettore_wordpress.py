# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Prova incrociata con il connettore WordPress (integrazioni/wordpress): il PHP
# *              firma e cifra, il gestionale verifica e decifra, e viceversa. Così le due
# *              implementazioni del contratto non possono divergere. Saltata senza php.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from apps.api import chiavi, jwe
from apps.api import firma as f

PLUGIN = Path(__file__).resolve().parents[3] / "integrazioni/wordpress/gestione-associazione"
PHP = shutil.which("php")
pytestmark = pytest.mark.skipif(PHP is None, reason="php non disponibile")


def php(**comando):
    # php locale e script del repository: nessun dato esterno nel comando
    uscita = subprocess.run(  # noqa: S603
        [PHP, str(PLUGIN / "tests/interop.php")],
        input=json.dumps(comando), capture_output=True, text=True, timeout=30, check=True,
    )  # fmt: skip
    risultato = json.loads(uscita.stdout)
    assert "errore" not in risultato, risultato.get("errore")
    return risultato


def test_test_del_plugin():
    uscita = subprocess.run(  # noqa: S603
        [PHP, str(PLUGIN / "tests/esegui.php")], capture_output=True, text=True, timeout=60
    )
    assert uscita.returncode == 0, uscita.stderr + uscita.stdout


def _x25519_jwk(privata):
    x = f.b64url(privata.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    jwk = {"kty": "OKP", "crv": "X25519", "x": x, "use": "enc"}
    jwk["kid"] = chiavi.thumbprint(jwk)
    return jwk


def test_jwe_dal_plugin_al_gestionale_e_ritorno():
    privata = X25519PrivateKey.generate()
    jwk = _x25519_jwk(privata)
    cifrato = php(comando="cifra", testo='{"nome":"Mario","città":"Potenza"}', jwk=jwk)["jwe"]
    assert jwe.decifra_json(cifrato, lambda kid: privata if kid == jwk["kid"] else None) == {
        "nome": "Mario", "città": "Potenza"}  # fmt: skip
    sito = php(comando="chiavi")
    chiave_sito = sito["jwks"]["keys"][1]
    risposta = jwe.cifra({"uuid": "x", "accompagnatori": 2}, chiave_sito)
    testo = php(comando="decifra", jwe=risposta, segreto=sito["chiavi"]["cifratura"])["testo"]
    assert json.loads(testo) == {"uuid": "x", "accompagnatori": 2}


def test_firma_del_plugin_verificata_dal_gestionale():
    sito = php(comando="chiavi")
    firma_jwk = sito["jwks"]["keys"][0]
    assert firma_jwk["kid"] == chiavi.thumbprint(firma_jwk)
    corpo = "eyJ.cifrato"
    intest = php(comando="firma_richiesta", metodo="POST", percorso="/api/v1/domande", query="",
                 destinatario="uuid-istanza", corpo=corpo, keyid=firma_jwk["kid"],
                 seme=sito["chiavi"]["firma"])["intestazioni"]  # fmt: skip
    msg = f.Messaggio(intestazioni={k.lower(): v for k, v in intest.items()}, metodo="POST",
                      percorso="/api/v1/domande", query="")  # fmt: skip
    assert f.verifica_digest(intest["Content-Digest"], corpo.encode())
    esito = f.verifica(msg, lambda kid: f.chiave_pubblica(firma_jwk["x"]),
                       richiesti=f.richiesti(f.componenti_richiesta(True)),
                       adesso=time.time())  # fmt: skip
    assert esito.keyid == firma_jwk["kid"]


def test_risposta_del_gestionale_verificata_dal_plugin():
    sito = php(comando="chiavi")
    firma_jwk = sito["jwks"]["keys"][0]
    intest = php(comando="firma_richiesta", metodo="GET", percorso="/api/v1/eventi",
                 query="dal=2027-01-01", destinatario="uuid-istanza", corpo=None,
                 keyid=firma_jwk["kid"], seme=sito["chiavi"]["firma"])["intestazioni"]  # fmt: skip
    richiesta = f.Messaggio(intestazioni={k.lower(): v for k, v in intest.items()}, metodo="GET",
                            percorso="/api/v1/eventi", query="dal=2027-01-01")  # fmt: skip
    istanza = Ed25519PrivateKey.generate()
    pubblica = {
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "x": f.b64url(istanza.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
    }
    pubblica["kid"] = chiavi.thumbprint(pubblica)
    corpo = b'{"risultati":[],"successivo":null}'
    risposta = f.Messaggio(intestazioni={"content-digest": f.content_digest(corpo)}, stato=200,
                           richiesta=richiesta)  # fmt: skip
    ingresso, valore = f.firma(
        risposta,
        f.componenti_risposta(True),
        f.parametri_firma(pubblica["kid"], time.time(), "r" * 20),
        istanza,
    )
    intestazioni = {"Content-Digest": f.content_digest(corpo), "Signature-Input": ingresso,
                    "Signature": valore}  # fmt: skip
    membro = intest["Signature"].split("=", 1)[1]
    assert php(
        comando="verifica_risposta",
        stato=200,
        intestazioni=intestazioni,
        corpo=corpo.decode(),
        firma_richiesta=membro,
        jwks={"keys": [pubblica]},
    )["valida"]
    with pytest.raises(AssertionError, match="non valida"):  # risposta riusata con un altro stato
        php(comando="verifica_risposta", stato=201, intestazioni=intestazioni, corpo=corpo.decode(),
            firma_richiesta=membro, jwks={"keys": [pubblica]})  # fmt: skip


def test_impronta_di_abbinamento_uguale():
    a, b = php(comando="chiavi")["jwks"], php(comando="chiavi")["jwks"]
    assert php(comando="impronta", a=a, b=b)["impronta"] == chiavi.impronta_abbinamento(a, b)
