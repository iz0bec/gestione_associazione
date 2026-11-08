<!--
******************************************************
* Progetto:    Gestione Associazione
* Autore:      Bartolomeo Santoro aka IZ0BEC
* Email:       info@iz0bec.info
* Descrizione: Primi passi: accesso e interfaccia
* Licenza:     CC0 1.0 Universal (pubblico dominio)
* SPDX-License-Identifier: CC0-1.0
******************************************************
-->

# Primi passi

## Accedere

1. Aprire l'indirizzo comunicato dall'amministratore.
2. In **Login** scrivere il nome utente oppure l'email; poi la password.
3. Se è attiva la verifica in due passaggi, inserire il codice a 6 cifre dell'app di
   autenticazione (oppure usare la passkey).

Dopo **5 tentativi sbagliati** l'accesso si blocca per 15 minuti, per proteggere l'account.
Se capita, attendere o rivolgersi all'amministratore.

**Password dimenticata?** Dal link nella pagina di accesso si riceve per email un collegamento
per sceglierne una nuova (serve che l'email dell'account sia corretta).

## La verifica in due passaggi (consigliata, obbligatoria per alcuni ruoli)

Protegge l'account anche se qualcuno scopre la password.

1. Menu utente in alto a destra → **Verifica in due passaggi**.
2. **App di autenticazione**: inquadrare il QR code con un'app come Google Authenticator,
   Microsoft Authenticator, Aegis o 2FAS, poi scrivere il codice mostrato per confermare.
3. Salvare i **codici di recupero** in un luogo sicuro (servono se si perde il telefono).
4. In alternativa o in aggiunta si può registrare una **passkey** (impronta, volto, PIN del
   dispositivo o chiavetta di sicurezza): poi si accede con *Accedi con una passkey*,
   senza password. Le passkey funzionano solo se il sito è in HTTPS.

## Com'è fatta l'interfaccia

- **Menu a sinistra**: i moduli. Si vedono solo quelli consentiti dal proprio ruolo.
  Su smartphone il menu si apre con il pulsante ☰.
- **Barra in alto**: ricerca rapida in anagrafica; nome e **versione** del programma (un clic apre
  *Informazioni*: autore, licenza, componenti di terze parti); pulsante **?** dell'aiuto; tema
  chiaro/scuro (🌙/☀); menu utente (cambio password, verifica in due passaggi, manuale,
  informazioni, esci).
- **Aiuto in linea**: il pulsante **?** apre la pagina di questo manuale dedicata alla sezione in
  cui ci si trova (es. da *Tesoreria* apre il manuale della tesoreria). Dalla pagina dell'aiuto si
  passa alle altre con l'indice a destra.
- **Cruscotto**: numeri principali, compleanni dei prossimi 14 giorni, le proprie ultime attività.

## Uscire

Menu utente → **Esci**. La sessione si chiude comunque chiudendo il browser e dopo 8 ore.
Su un computer condiviso uscire sempre.
