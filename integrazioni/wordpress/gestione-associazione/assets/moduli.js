/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Rinnova al caricamento della pagina il gettone anti-spam dei moduli (ora di
 *              presentazione firmata), così una pagina servita dalla cache non scade dopo 3 ore.
 *              Senza JavaScript resta valido il gettone scritto nella pagina.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */
( function () {
	if ( ! window.fetch ) {
		return;
	}
	document.querySelectorAll( 'form.ga-modulo[data-ga-gettone]' ).forEach( function ( modulo ) {
		var gettone = modulo.querySelector( 'input[name="ga_t"]' );
		var nome = modulo.querySelector( 'input[name="ga_modulo"]' );
		if ( ! gettone || ! nome ) {
			return;
		}
		var indirizzo = modulo.getAttribute( 'data-ga-gettone' );
		indirizzo += ( indirizzo.indexOf( '?' ) < 0 ? '?' : '&' ) + 'modulo=' + encodeURIComponent( nome.value );
		fetch( indirizzo, { credentials: 'omit', cache: 'no-store' } )
			.then( function ( r ) { return r.ok ? r.json() : null; } )
			.then( function ( dati ) {
				if ( dati && typeof dati.t === 'string' ) {
					gettone.value = dati.t;
				}
			} )
			.catch( function () {} );
	} );
}() );
