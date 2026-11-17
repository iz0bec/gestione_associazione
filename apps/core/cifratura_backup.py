# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Cifratura dei backup con la chiave dedicata CHIAVE_BACKUP: AES-256-GCM a
# *              blocchi da 1 MiB (file grandi senza tenerli in memoria), numero del blocco nel
# *              nonce e marcatura dell'ultimo blocco (troncamenti e scambi si scoprono).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import hashlib
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

MAGIA = b"GABK"
VERSIONE = 1
BLOCCO = 1024 * 1024
_TESTA = struct.Struct(">4sB8s4s")  # magia, versione, impronta della chiave, prefisso del nonce
_LUNGHEZZA = struct.Struct(">I")


class ErroreCifratura(Exception):
    pass


def nuova_chiave():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _byte(chiave):
    try:
        dati = base64.urlsafe_b64decode(chiave.encode())
    except (ValueError, TypeError) as e:
        raise ErroreCifratura("CHIAVE_BACKUP non valida.") from e
    if len(dati) != 32:
        raise ErroreCifratura("CHIAVE_BACKUP non valida (servono 32 byte in base64).")
    return dati


def chiave_corrente():
    """La chiave dei backup, o "" se non configurata (backup in chiaro)."""
    return (getattr(settings, "CHIAVE_BACKUP", "") or "").strip()


def impronta(chiave):
    """Impronta breve della chiave, per riconoscerla senza rivelarla."""
    return hashlib.sha256(_byte(chiave)).hexdigest()[:16]


def _nonce(prefisso, numero):
    return prefisso + struct.pack(">Q", numero)


def cifra(sorgente, destinazione, chiave):
    """Cifra il file sorgente nel file destinazione. Restituisce lo SHA-256 del contenuto in
    chiaro (lo stesso usato per verificare il backup)."""
    aes = AESGCM(_byte(chiave))
    prefisso = os.urandom(4)
    h = hashlib.sha256()
    with open(sorgente, "rb") as src, open(destinazione, "wb") as dst:
        dst.write(_TESTA.pack(MAGIA, VERSIONE, bytes.fromhex(impronta(chiave)), prefisso))
        numero = 0
        blocco = src.read(BLOCCO)
        while True:
            seguente = src.read(BLOCCO)
            ultimo = not seguente
            h.update(blocco)
            cifrato = aes.encrypt(_nonce(prefisso, numero), blocco, b"ultimo" if ultimo else b"")
            dst.write(_LUNGHEZZA.pack(len(cifrato)) + cifrato)
            if ultimo:
                break
            blocco, numero = seguente, numero + 1
    return h.hexdigest()


def decifra_flusso(sorgente, chiave):
    """Blocchi in chiaro letti da un file aperto (anche dentro un .tar); solleva
    ErroreCifratura se la chiave è sbagliata o il file è danneggiato o troncato."""
    testa = sorgente.read(_TESTA.size)
    if len(testa) != _TESTA.size:
        raise ErroreCifratura("File cifrato troncato.")
    magia, versione, impronta_file, prefisso = _TESTA.unpack(testa)
    if magia != MAGIA or versione != VERSIONE:
        raise ErroreCifratura("Non è un file cifrato dei backup.")
    if not chiave:
        raise ErroreCifratura(
            f"Il backup è cifrato: serve la chiave CHIAVE_BACKUP (impronta {impronta_file.hex()})."
        )
    if impronta_file.hex() != impronta(chiave):
        raise ErroreCifratura(
            f"Il backup è cifrato con un'altra chiave (impronta {impronta_file.hex()}, quella "
            f"configurata è {impronta(chiave)})."
        )
    aes = AESGCM(_byte(chiave))
    numero = 0
    while True:
        lunghezza = sorgente.read(_LUNGHEZZA.size)
        if len(lunghezza) != _LUNGHEZZA.size:
            raise ErroreCifratura("File cifrato troncato.")
        (n,) = _LUNGHEZZA.unpack(lunghezza)
        if n > BLOCCO + 16:
            raise ErroreCifratura("File cifrato danneggiato.")
        cifrato = sorgente.read(n)
        if len(cifrato) != n:
            raise ErroreCifratura("File cifrato troncato.")
        for aad, ultimo in ((b"", False), (b"ultimo", True)):
            try:
                chiaro = aes.decrypt(_nonce(prefisso, numero), cifrato, aad)
            except InvalidTag:
                continue
            yield chiaro
            if ultimo:
                if sorgente.read(1):
                    raise ErroreCifratura("Dati in più dopo la fine del file cifrato.")
                return
            break
        else:
            raise ErroreCifratura("File cifrato danneggiato o chiave errata.")
        numero += 1


def decifra(sorgente, destinazione, chiave):
    """Decifra un file in un altro. Restituisce lo SHA-256 del contenuto in chiaro."""
    h = hashlib.sha256()
    with open(sorgente, "rb") as src, open(destinazione, "wb") as dst:
        for blocco in decifra_flusso(src, chiave):
            h.update(blocco)
            dst.write(blocco)
    return h.hexdigest()


def e_cifrato(file_aperto):
    """Il file (aperto, all'inizio) è cifrato? Non sposta la posizione di lettura."""
    pos = file_aperto.tell()
    magia = file_aperto.read(4)
    file_aperto.seek(pos)
    return magia == MAGIA
