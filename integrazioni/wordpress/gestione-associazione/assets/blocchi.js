/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Blocchi dell'editor (senza compilazione): domanda, contatti, eventi,
 *              organigramma, verifica tessera, con l'anteprima impaginata dal server.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */
( function ( wp ) {
	var el = wp.element.createElement;
	var Testo = wp.components.TextControl;
	var Pannello = wp.components.PanelBody;
	var Inspector = wp.blockEditor.InspectorControls;
	var Anteprima = wp.serverSideRender;
	var blocchi = {
		'domanda': { titolo: 'Domanda di iscrizione', icona: 'id', campi: { sezione: 'Codice della sezione', statuto: 'Indirizzo dello statuto', informativa: 'Indirizzo dell\'informativa' } },
		'contatti': { titolo: 'Modulo contatti', icona: 'email', campi: {} },
		'eventi': { titolo: 'Eventi con adesione', icona: 'calendar-alt', campi: { quanti: 'Quanti eventi' } },
		'organigramma': { titolo: 'Organigramma', icona: 'groups', campi: { sezione: 'Codice della sezione (vuoto: l\'ente)' } },
		'verifica-tessera': { titolo: 'Verifica della tessera', icona: 'yes-alt', campi: {} },
		'calendario': { titolo: 'Calendario degli eventi', icona: 'calendar', campi: { vista: 'Vista iniziale (lista, mese, giorno)', quanti: 'Quanti eventi nell\'elenco' } },
		'prossimi-eventi': { titolo: 'Prossimi eventi', icona: 'list-view', campi: { quanti: 'Quanti eventi' } }
	};
	Object.keys( blocchi ).forEach( function ( nome ) {
		var b = blocchi[ nome ];
		var attributi = {};
		Object.keys( b.campi ).forEach( function ( c ) { attributi[ c ] = { type: c === 'quanti' ? 'number' : 'string' }; } );
		wp.blocks.registerBlockType( 'gestione-associazione/' + nome, {
			title: b.titolo,
			icon: b.icona,
			category: 'widgets',
			attributes: attributi,
			edit: function ( props ) {
				var controlli = Object.keys( b.campi ).map( function ( c ) {
					return el( Testo, {
						key: c, label: b.campi[ c ], value: props.attributes[ c ] || '',
						type: c === 'quanti' ? 'number' : 'text',
						onChange: function ( v ) { var o = {}; o[ c ] = c === 'quanti' ? parseInt( v, 10 ) || undefined : v; props.setAttributes( o ); }
					} );
				} );
				return [
					controlli.length ? el( Inspector, { key: 'i' }, el( Pannello, { title: 'Gestione Associazione' }, controlli ) ) : null,
					el( Anteprima, { key: 'a', block: 'gestione-associazione/' + nome, attributes: props.attributes } )
				];
			},
			save: function () { return null; }
		} );
	} );
} )( window.wp );
