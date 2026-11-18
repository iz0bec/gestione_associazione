# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Firma dei messaggi HTTP (RFC 9421, ed25519), campi strutturati (RFC 8941, solo
# *              quanto serve alla firma) e Content-Digest (RFC 9530). Nessuna dipendenza da
# *              Django: lo usano sia le viste dell'API sia il client verso le altre installazioni.
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ETICHETTA = "ga"
TAG = "ga-v1"
TOLLERANZA_SECONDI = 300


class ErroreFirma(Exception):
    """Firma assente, malformata o non valida. `codice` è quello dei Problem Details."""

    def __init__(self, codice, messaggio):
        super().__init__(messaggio)
        self.codice = codice
        self.messaggio = messaggio


# ---------------------------------------------------------------- campi strutturati (RFC 8941)


class Token(str):
    """Token dei campi strutturati (distinto dalle stringhe tra virgolette)."""


_CHIAVE = re.compile(r"[a-z*][a-z0-9_\-.*]*")
_TOKEN = re.compile(r"[A-Za-z*][!#$%&'*+\-.^_`|~0-9A-Za-z:/]*")
_INTERO = re.compile(r"-?[0-9]{1,15}")
_BASE64 = re.compile(r"[A-Za-z0-9+/=]*")


class _Lettore:
    def __init__(self, testo):
        if not isinstance(testo, str) or not testo.isascii():
            raise ValueError("campo strutturato non ASCII")
        self.t = testo
        self.i = 0

    def fine(self):
        return self.i >= len(self.t)

    def car(self):
        return self.t[self.i] if self.i < len(self.t) else ""

    def spazi(self):
        while self.car() == " ":
            self.i += 1

    def ows(self):
        while self.car() in (" ", "\t") and not self.fine():
            self.i += 1

    def _regex(self, regex, cosa):
        m = regex.match(self.t, self.i)
        if not m:
            raise ValueError(f"{cosa} non valido alla posizione {self.i}")
        self.i = m.end()
        return m.group(0)

    def chiave(self):
        return self._regex(_CHIAVE, "nome")

    def stringa(self):
        self.i += 1  # virgolette iniziali
        risultato = []
        while not self.fine():
            c = self.car()
            self.i += 1
            if c == "\\":
                c = self.car()
                if c not in ('"', "\\"):
                    raise ValueError("escape non valido in una stringa")
                self.i += 1
                risultato.append(c)
            elif c == '"':
                return "".join(risultato)
            elif not (0x20 <= ord(c) <= 0x7E):
                raise ValueError("carattere non valido in una stringa")
            else:
                risultato.append(c)
        raise ValueError("stringa non chiusa")

    def byte(self):
        self.i += 1
        dati = self._regex(_BASE64, "sequenza di byte")
        if self.car() != ":":
            raise ValueError("sequenza di byte non chiusa")
        self.i += 1
        try:
            return base64.b64decode(dati, validate=True)
        except ValueError as e:
            raise ValueError("base64 non valido") from e

    def elemento(self):
        c = self.car()
        if c == '"':
            return self.stringa()
        if c == ":":
            return self.byte()
        if c == "?":
            self.i += 1
            valore = self.car()
            if valore not in ("0", "1"):
                raise ValueError("booleano non valido")
            self.i += 1
            return valore == "1"
        if c == "-" or c.isdigit():
            valore = self._regex(_INTERO, "intero")
            if self.car() == ".":
                raise ValueError("numeri decimali non ammessi")
            return int(valore)
        return Token(self._regex(_TOKEN, "token"))

    def parametri(self):
        parametri = []
        while self.car() == ";":
            self.i += 1
            self.spazi()
            nome = self.chiave()
            valore = True
            if self.car() == "=":
                self.i += 1
                valore = self.elemento()
            parametri = [(n, v) for n, v in parametri if n != nome] + [(nome, valore)]
        return parametri

    def lista_interna(self):
        self.i += 1  # "("
        elementi = []
        while not self.fine():
            self.spazi()
            if self.car() == ")":
                self.i += 1
                return elementi, self.parametri()
            elementi.append((self.elemento(), self.parametri()))
            if self.car() not in (" ", ")"):
                raise ValueError("lista interna non valida")
        raise ValueError("lista interna non chiusa")

    def dizionario(self):
        risultato = {}
        self.spazi()
        while not self.fine():
            nome = self.chiave()
            if self.car() == "=":
                self.i += 1
                membro = self.lista_interna() if self.car() == "(" else (self.elemento(), None)
                if membro[1] is None:
                    membro = (membro[0], self.parametri())
            else:
                membro = (True, self.parametri())
            risultato[nome] = membro
            self.ows()
            if self.fine():
                break
            if self.car() != ",":
                raise ValueError("dizionario non valido")
            self.i += 1
            self.ows()
            if self.fine():
                raise ValueError("virgola finale nel dizionario")
        return risultato


def leggi_dizionario(testo):
    """Dizionario RFC 8941: {nome: (valore | [(elemento, parametri)], parametri)}."""
    return _Lettore(testo.strip(" ")).dizionario()


def scrivi_elemento(valore):
    if isinstance(valore, bool):
        return "?1" if valore else "?0"
    if isinstance(valore, int):
        return str(valore)
    if isinstance(valore, bytes):
        return ":" + base64.b64encode(valore).decode() + ":"
    if isinstance(valore, Token):
        return str(valore)
    if isinstance(valore, str):
        if not all(0x20 <= ord(c) <= 0x7E for c in valore):
            raise ValueError("stringa non serializzabile")
        return '"' + valore.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise TypeError(f"valore non serializzabile: {valore!r}")


def scrivi_parametri(parametri):
    parti = []
    for nome, valore in parametri:
        parti.append(f";{nome}" if valore is True else f";{nome}={scrivi_elemento(valore)}")
    return "".join(parti)


def scrivi_lista_interna(elementi, parametri):
    interno = " ".join(scrivi_elemento(v) + scrivi_parametri(p) for v, p in elementi)
    return f"({interno})" + scrivi_parametri(parametri)


# ---------------------------------------------------------------- Content-Digest (RFC 9530)


def content_digest(corpo: bytes) -> str:
    return "sha-256=" + scrivi_elemento(hashlib.sha256(corpo).digest())


def verifica_digest(intestazione: str, corpo: bytes) -> bool:
    """Vero se l'intestazione contiene sha-256 e corrisponde al corpo (gli altri algoritmi
    sono ignorati: sha-256 è obbligatorio nel contratto)."""
    try:
        valori = leggi_dizionario(intestazione)
    except ValueError:
        return False
    atteso = valori.get("sha-256", (None, None))[0]
    if not isinstance(atteso, bytes):
        return False
    return hmac.compare_digest(atteso, hashlib.sha256(corpo).digest())


# ---------------------------------------------------------------- firma (RFC 9421)


@dataclass
class Messaggio:
    """Vista neutra di un messaggio HTTP: richiesta (metodo/percorso) o risposta (stato)."""

    intestazioni: dict = field(default_factory=dict)  # nomi in minuscolo
    metodo: str = ""
    percorso: str = ""
    query: str = ""  # senza "?"
    autorita: str = ""
    stato: int | None = None
    richiesta: "Messaggio | None" = None  # per i componenti con ;req

    def intestazione(self, nome):
        return self.intestazioni.get(nome.lower())


@dataclass
class FirmaVerificata:
    keyid: str
    componenti: list
    parametri: dict
    etichetta: str


def _valore_componente(msg: Messaggio, nome: str, parametri: list) -> str:
    opzioni = dict(parametri)
    if opzioni.pop("req", False):
        if msg.richiesta is None:
            raise ErroreFirma("firma-non-valida", f"Componente {nome};req senza richiesta.")
        msg = msg.richiesta
    if nome.startswith("@"):
        if opzioni:
            raise ErroreFirma("firma-non-valida", f"Parametri non ammessi su {nome}.")
        valori = {
            "@method": msg.metodo,
            "@path": msg.percorso or "/",
            "@query": "?" + msg.query,
            "@authority": msg.autorita.lower(),
            "@status": str(msg.stato) if msg.stato is not None else None,
        }
        valore = valori.get(nome)
        if valore is None or (nome != "@status" and not msg.metodo):
            raise ErroreFirma("firma-non-valida", f"Componente {nome} non disponibile.")
        return valore
    grezzo = msg.intestazione(nome)
    if grezzo is None:
        raise ErroreFirma("firma-non-valida", f"Intestazione firmata mancante: {nome}.")
    if "key" in opzioni:
        chiave = opzioni.pop("key")
        try:
            dizionario = leggi_dizionario(grezzo)
        except ValueError as e:
            raise ErroreFirma("firma-non-valida", f"{nome} non è un dizionario.") from e
        if chiave not in dizionario:
            raise ErroreFirma("firma-non-valida", f"{nome} senza la chiave {chiave}.")
        valore, param = dizionario[chiave]
        grezzo = (
            scrivi_lista_interna(valore, param)
            if isinstance(valore, list)
            else scrivi_elemento(valore) + scrivi_parametri(param)
        )
    if opzioni:
        raise ErroreFirma("firma-non-valida", f"Parametri non supportati su {nome}.")
    return " ".join(parte.strip() for parte in grezzo.split("\n")).strip()


def base_firma(msg: Messaggio, componenti: list, parametri: list) -> bytes:
    """Base della firma (RFC 9421 §2.5). `componenti`: [(nome, parametri)]."""
    righe = []
    visti = set()
    for nome, param in componenti:
        identificatore = scrivi_elemento(nome) + scrivi_parametri(param)
        if identificatore in visti:
            raise ErroreFirma("firma-non-valida", f"Componente ripetuto: {identificatore}.")
        visti.add(identificatore)
        righe.append(f"{identificatore}: {_valore_componente(msg, nome, param)}")
    righe.append('"@signature-params": ' + scrivi_lista_interna(componenti, parametri))
    return "\n".join(righe).encode("ascii")


def firma(msg, componenti, parametri, chiave: Ed25519PrivateKey, etichetta=ETICHETTA):
    """Restituisce (Signature-Input, Signature) da aggiungere al messaggio."""
    componenti = [(nome, list(p)) for nome, p in componenti]
    valore = chiave.sign(base_firma(msg, componenti, parametri))
    return (
        f"{etichetta}=" + scrivi_lista_interna(componenti, parametri),
        f"{etichetta}=" + scrivi_elemento(valore),
    )


def leggi_firma(msg: Messaggio, etichetta=ETICHETTA):
    """(componenti, parametri, valore) della firma con l'etichetta indicata."""
    ingresso = msg.intestazione("signature-input")
    firme = msg.intestazione("signature")
    if not ingresso or not firme:
        raise ErroreFirma("firma-non-valida", "Firma assente (Signature e Signature-Input).")
    try:
        ingressi = leggi_dizionario(ingresso)
        valori = leggi_dizionario(firme)
    except ValueError as e:
        raise ErroreFirma("firma-non-valida", f"Firma malformata: {e}.") from e
    if etichetta not in ingressi or etichetta not in valori:
        raise ErroreFirma("firma-non-valida", f'Manca la firma con etichetta "{etichetta}".')
    componenti, parametri = ingressi[etichetta]
    valore = valori[etichetta][0]
    if not isinstance(componenti, list) or not isinstance(valore, bytes):
        raise ErroreFirma("firma-non-valida", "Firma malformata.")
    if not all(isinstance(nome, str) and not isinstance(nome, Token) for nome, _ in componenti):
        raise ErroreFirma("firma-non-valida", "Componenti della firma non validi.")
    return componenti, parametri, valore


def verifica(msg, chiave_per_keyid, *, richiesti, adesso, etichetta=ETICHETTA, con_tempi=True):
    """Verifica la firma `etichetta` del messaggio.

    `chiave_per_keyid(keyid)` restituisce la Ed25519PublicKey o None; `richiesti` sono i nomi
    dei componenti che devono essere coperti. Con `con_tempi` servono created/expires/nonce,
    alg="ed25519" e tag="ga-v1" (il profilo del contratto)."""
    componenti, parametri, valore = leggi_firma(msg, etichetta)
    param = dict(parametri)
    coperti = {scrivi_elemento(nome) + scrivi_parametri(p) for nome, p in componenti}
    mancanti = [r for r in richiesti if r not in coperti]
    if mancanti:
        raise ErroreFirma("firma-non-valida", f"Componenti non firmati: {', '.join(mancanti)}.")
    keyid = param.get("keyid")
    if not isinstance(keyid, str) or not keyid:
        raise ErroreFirma("firma-non-valida", "Parametro keyid mancante.")
    if con_tempi:
        if param.get("alg") != "ed25519":
            raise ErroreFirma("firma-non-valida", 'Serve alg="ed25519".')
        if param.get("tag") != TAG:
            raise ErroreFirma("firma-non-valida", f'Serve tag="{TAG}".')
        creata, scade = param.get("created"), param.get("expires")
        if not isinstance(creata, int) or not isinstance(scade, int):
            raise ErroreFirma("firma-non-valida", "Servono i parametri created ed expires.")
        if abs(adesso - creata) > TOLLERANZA_SECONDI:
            raise ErroreFirma(
                "firma-scaduta",
                f"Orologio fuori tolleranza: scarto di {int(adesso - creata)} secondi "
                f"(massimo {TOLLERANZA_SECONDI}).",
            )
        if scade < creata or scade - creata > TOLLERANZA_SECONDI or adesso > scade:
            raise ErroreFirma("firma-scaduta", "Firma scaduta (expires).")
        nonce = param.get("nonce")
        if not isinstance(nonce, str) or not 16 <= len(nonce) <= 64:
            raise ErroreFirma("firma-non-valida", "Serve un nonce di 16-64 caratteri.")
    chiave = chiave_per_keyid(keyid)
    if chiave is None:
        raise ErroreFirma("firma-non-valida", f"Chiave sconosciuta: {keyid}.")
    try:
        chiave.verify(valore, base_firma(msg, componenti, parametri))
    except InvalidSignature as e:
        raise ErroreFirma("firma-non-valida", "Firma non valida.") from e
    return FirmaVerificata(keyid, componenti, param, etichetta)


def componenti_richiesta(con_corpo: bool):
    """Componenti firmati dal contratto per le richieste."""
    nomi = ["@method", "@path", "@query", "destinatario-istanza"]
    if con_corpo:
        nomi.append("content-digest")
    return [(n, []) for n in nomi]


def componenti_risposta(con_richiesta_firmata: bool):
    componenti = [("@status", []), ("content-digest", [])]
    if con_richiesta_firmata:
        componenti.append(("signature", [("req", True), ("key", ETICHETTA)]))
    return componenti


def richiesti(componenti):
    return [scrivi_elemento(n) + scrivi_parametri(p) for n, p in componenti]


def parametri_firma(keyid, adesso, nonce, durata=TOLLERANZA_SECONDI):
    return [
        ("created", int(adesso)),
        ("expires", int(adesso) + durata),
        ("nonce", nonce),
        ("keyid", keyid),
        ("alg", "ed25519"),
        ("tag", TAG),
    ]


def chiave_pubblica(x_b64url: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(b64url_decodifica(x_b64url))


def b64url(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).rstrip(b"=").decode()


def b64url_decodifica(testo: str) -> bytes:
    if not isinstance(testo, str) or not re.fullmatch(r"[A-Za-z0-9_-]*", testo):
        raise ValueError("base64url non valido")
    return base64.urlsafe_b64decode(testo + "=" * (-len(testo) % 4))
