# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Test della firma RFC 9421 con i vettori ufficiali (Appendice B.2.6), del
# *              Content-Digest (RFC 9530) e del lettore dei campi strutturati (RFC 8941).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from apps.api import firma as f

# RFC 9421, Appendice B.1.4 (test-key-ed25519)
CHIAVE_RFC = load_pem_private_key(
    b"-----BEGIN PRIVATE KEY-----\n"
    b"MC4CAQAwBQYDK2VwBCIEIJ+DYvh6SEqVTm50DFtMDoQikTmiCqirVv9mWG9qfSnF\n"
    b"-----END PRIVATE KEY-----\n",
    None,
)
FIRMA_B26 = "sig-b26=:wqcAqbmYJ2ji2glfAMaRy4gruYYnx2nEFN2HN6jrnDnQCK1u02Gb04v9EDgwUPiu4A0w6vuQv5lIp5WPpBKRCw==:"
COMPONENTI_B26 = [
    (n, []) for n in ("date", "@method", "@path", "@authority", "content-type", "content-length")
]


def _richiesta_rfc():
    return f.Messaggio(
        intestazioni={
            "date": "Tue, 20 Apr 2021 02:07:55 GMT",
            "content-type": "application/json",
            "content-length": "18",
        },
        metodo="POST",
        percorso="/foo",
        query="param=Value&Pet=dog",
        autorita="example.com",
    )


def test_vettore_rfc9421_b26():
    msg = _richiesta_rfc()
    parametri = [("created", 1618884473), ("keyid", "test-key-ed25519")]
    assert f.base_firma(msg, COMPONENTI_B26, parametri).decode() == (
        '"date": Tue, 20 Apr 2021 02:07:55 GMT\n'
        '"@method": POST\n'
        '"@path": /foo\n'
        '"@authority": example.com\n'
        '"content-type": application/json\n'
        '"content-length": 18\n'
        '"@signature-params": ("date" "@method" "@path" "@authority" "content-type" '
        '"content-length");created=1618884473;keyid="test-key-ed25519"'
    )
    ingresso, valore = f.firma(msg, COMPONENTI_B26, parametri, CHIAVE_RFC, "sig-b26")
    assert valore == FIRMA_B26
    assert ingresso == (
        'sig-b26=("date" "@method" "@path" "@authority" "content-type" "content-length")'
        ';created=1618884473;keyid="test-key-ed25519"'
    )


def test_verifica_del_vettore_rfc_e_alterazioni():
    msg = _richiesta_rfc()
    msg.intestazioni["signature-input"] = (
        'sig-b26=("date" "@method" "@path" "@authority" "content-type" "content-length")'
        ';created=1618884473;keyid="test-key-ed25519"'
    )
    msg.intestazioni["signature"] = FIRMA_B26
    pubblica = CHIAVE_RFC.public_key()
    esito = f.verifica(msg, lambda kid: pubblica, richiesti=['"@path"'], adesso=0,
                       etichetta="sig-b26", con_tempi=False)  # fmt: skip
    assert esito.keyid == "test-key-ed25519"
    msg.percorso = "/bar"
    with pytest.raises(f.ErroreFirma, match="non valida"):
        f.verifica(msg, lambda kid: pubblica, richiesti=[], adesso=0, etichetta="sig-b26",
                   con_tempi=False)  # fmt: skip


def test_content_digest_rfc9530():
    corpo = b'{"hello": "world"}'
    assert f.content_digest(corpo) == "sha-256=:X48E9qOokqqrvdts8nOJRJN3OWDUoyWxBf7kbu9DBPE=:"
    assert f.verifica_digest("sha-256=:X48E9qOokqqrvdts8nOJRJN3OWDUoyWxBf7kbu9DBPE=:", corpo)
    assert not f.verifica_digest("sha-256=:X48E9qOokqqrvdts8nOJRJN3OWDUoyWxBf7kbu9DBPE=:", b"{}")
    assert not f.verifica_digest("sha-512=:AAAA:", corpo)
    assert not f.verifica_digest("non valido", corpo)


def test_campi_strutturati():
    d = f.leggi_dizionario('a=("x" "y";req;key="k");n=1;s="v\\"w", b=:AQID:, c, d=?0, e=tok/1')
    assert d["a"] == ([("x", []), ("y", [("req", True), ("key", "k")])], [("n", 1), ("s", 'v"w')])
    assert d["b"] == (b"\x01\x02\x03", [])
    assert d["c"] == (True, [])
    assert d["d"] == (False, [])
    assert isinstance(d["e"][0], f.Token)
    for errato in ('a=("x"', 'a="non chiusa', "a=1.5", "A=1", "a=:@@:", "a=1,", 'a="\\x"'):
        with pytest.raises(ValueError):
            f.leggi_dizionario(errato)
    assert f.scrivi_lista_interna([("x", [])], [("s", 'a"b\\')]) == '("x");s="a\\"b\\\\"'


def _firmato(adesso, **sovrascritti):
    chiave = Ed25519PrivateKey.generate()
    msg = f.Messaggio(intestazioni={"destinatario-istanza": "u"}, metodo="POST", percorso="/p")
    parametri = dict(f.parametri_firma("k1", adesso, "n" * 20))
    parametri.update(sovrascritti)
    ingresso, valore = f.firma(msg, f.componenti_richiesta(False), list(parametri.items()), chiave)
    msg.intestazioni.update({"signature-input": ingresso, "signature": valore})
    return msg, chiave.public_key()


def test_profilo_del_contratto():
    richiesti = f.richiesti(f.componenti_richiesta(False))
    msg, pub = _firmato(1000)
    assert f.verifica(msg, lambda k: pub, richiesti=richiesti, adesso=1100).keyid == "k1"
    with pytest.raises(f.ErroreFirma) as e:
        f.verifica(msg, lambda k: pub, richiesti=richiesti, adesso=1400)
    assert e.value.codice == "firma-scaduta"
    with pytest.raises(f.ErroreFirma, match="sconosciuta"):
        f.verifica(msg, lambda k: None, richiesti=richiesti, adesso=1100)
    with pytest.raises(f.ErroreFirma, match="non firmati"):
        f.verifica(msg, lambda k: pub, richiesti=[*richiesti, '"content-digest"'], adesso=1100)
    for errato in ({"alg": "rsa-pss-sha512"}, {"tag": "altro"}, {"nonce": "corto"},
                   {"expires": 5000}):  # fmt: skip
        msg, pub = _firmato(1000, **errato)
        with pytest.raises(f.ErroreFirma):
            f.verifica(msg, lambda k, pub=pub: pub, richiesti=richiesti, adesso=1100)


def test_risposta_legata_alla_richiesta():
    richiesta, _ = _firmato(1000)
    chiave = Ed25519PrivateKey.generate()
    risposta = f.Messaggio(intestazioni={"content-digest": f.content_digest(b"{}")}, stato=200,
                           richiesta=richiesta)  # fmt: skip
    componenti = f.componenti_risposta(True)
    ingresso, valore = f.firma(risposta, componenti, f.parametri_firma("s", 1000, "m" * 20), chiave)
    risposta.intestazioni.update({"signature-input": ingresso, "signature": valore})
    richiesti = f.richiesti(componenti)
    assert '"signature";req;key="ga"' in richiesti
    f.verifica(risposta, lambda k: chiave.public_key(), richiesti=richiesti, adesso=1000)
    altra, _ = _firmato(1000)  # stessa risposta riusata per un'altra richiesta: rifiutata
    risposta.richiesta = altra
    with pytest.raises(f.ErroreFirma):
        f.verifica(risposta, lambda k: chiave.public_key(), richiesti=richiesti, adesso=1000)
