<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Impostazioni → Gestione Associazione: abbinamento con l'invito del gestionale,
 *              impronta da confrontare per una seconda via, prova del collegamento, articoli
 *              degli eventi, coda degli invii, aggiornamento di eventi e organigramma.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class GA_Amministrazione {

	const PAGINA = 'gestione-associazione';

	public static function avvia(): void {
		add_action( 'admin_menu', function () {
			add_options_page( __( 'Gestione Associazione', 'gestione-associazione' ), __( 'Gestione Associazione', 'gestione-associazione' ),
				'manage_options', self::PAGINA, array( __CLASS__, 'pagina' ) );
		} );
		add_action( 'admin_post_ga_azione', array( __CLASS__, 'azione' ) );
	}

	private static function torna( string $tipo, string $messaggio ): void {
		set_transient( 'ga_avviso_' . get_current_user_id(), array( $tipo, $messaggio ), 60 );
		wp_safe_redirect( admin_url( 'options-general.php?page=' . self::PAGINA ) );
		exit;
	}

	public static function azione(): void {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'Permesso negato.', 'gestione-associazione' ), 403 );
		}
		check_admin_referer( 'ga_azione' );
		$azione = sanitize_key( wp_unslash( $_POST['azione'] ?? '' ) );
		try {
			switch ( $azione ) {
				case 'abbina':
					$esito = GA_Connettore::abbina(
						sanitize_text_field( wp_unslash( $_POST['indirizzo'] ?? '' ) ),
						sanitize_text_field( wp_unslash( $_POST['invito'] ?? '' ) ),
						sanitize_text_field( wp_unslash( $_POST['nome'] ?? get_bloginfo( 'name' ) ) )
					);
					self::torna( 'success', sprintf( __( 'Abbinamento registrato. Comunicate all\'amministratore del gestionale l\'impronta %s: la confronta con la sua e attiva il collegamento.', 'gestione-associazione' ), $esito['impronta'] ?? GA_Connettore::impronta() ) );
					break;
				case 'prova':
					$d = GA_Connettore::prova();
					self::torna( 'info', sprintf( __( 'Firma %1$s; scarto dell\'orologio %2$d secondi; collegamento %3$s; ambiti: %4$s.', 'gestione-associazione' ),
						$d['firma'] ?? '?', (int) ( $d['orologio']['scarto_secondi'] ?? 0 ), $d['controparte']['stato'] ?? '?',
						implode( ', ', $d['controparte']['ambiti'] ?? array() ) ?: '-' ) );
					break;
				case 'aggiorna':
					$eventi = GA_Eventi::aggiorna_cache();
					list( $creati, $aggiornati ) = GA_Eventi::sincronizza_articoli();
					$inviati = GA_Connettore::svuota_coda();
					self::torna( 'success', sprintf( __( '%1$d eventi letti; eventi del sito: %2$d creati, %3$d aggiornati; invii in coda consegnati: %4$d.', 'gestione-associazione' ), count( $eventi ), $creati, $aggiornati, $inviati ) );
					break;
				case 'articoli':
					$prima = GA_Eventi::impostazioni();
					$modo  = sanitize_key( wp_unslash( $_POST['modo'] ?? 'calendario' ) );
					$nuove = array(
						'modo'          => in_array( $modo, array( 'calendario', 'articoli', 'nessuno' ), true ) ? $modo : 'calendario',
						'attivi'        => 'nessuno' !== $modo,
						'stato'         => 'publish' === ( $_POST['stato'] ?? '' ) ? 'publish' : 'draft',
						'categoria'     => sanitize_text_field( wp_unslash( $_POST['categoria'] ?? '' ) ),
						'autore'        => (int) ( $_POST['autore'] ?? 0 ),
						'slug_archivio' => sanitize_title( wp_unslash( $_POST['slug_archivio'] ?? '' ) ) ?: $prima['slug_archivio'],
						'slug_evento'   => sanitize_title( wp_unslash( $_POST['slug_evento'] ?? '' ) ) ?: $prima['slug_evento'],
					);
					foreach ( array( 'modo', 'slug_archivio', 'slug_evento' ) as $chiave ) {
						if ( $nuove[ $chiave ] !== $prima[ $chiave ] ) {
							update_option( 'ga_calendario_flush', 1, false );  // nuove regole degli indirizzi
						}
					}
					update_option( 'ga_articoli', $nuove, false );
					self::torna( 'success', __( 'Impostazioni degli eventi salvate.', 'gestione-associazione' ) );
					break;
				case 'riprova_coda':
					$n = GA_Connettore::riprova_coda();
					$inviati = GA_Connettore::abbinato() ? GA_Connettore::svuota_coda() : 0;
					self::torna( 'success', sprintf( __( 'Invii rimessi in coda: %1$d; consegnati ora: %2$d.', 'gestione-associazione' ), $n, $inviati ) );
					break;
				case 'elimina_voce':
					$tolta = GA_Connettore::elimina_voce( sanitize_text_field( wp_unslash( $_POST['chiave'] ?? '' ) ) );
					self::torna( $tolta ? 'warning' : 'error', $tolta
						? __( 'Invio eliminato: quei dati non arriveranno al gestionale.', 'gestione-associazione' )
						: __( 'Invio non trovato.', 'gestione-associazione' ) );
					break;
				case 'scollega':
					GA_Connettore::scollega();
					self::torna( 'warning', __( 'Collegamento tolto da questo sito. Revocate anche la controparte nel gestionale.', 'gestione-associazione' ) );
					break;
			}
		} catch ( GA_Errore_Connettore $e ) {
			self::torna( 'error', $e->getMessage() );
		}
		self::torna( 'error', __( 'Azione sconosciuta.', 'gestione-associazione' ) );
	}

	private static function modulo( string $azione, string $contenuto, string $pulsante, string $classe = 'button-primary' ): string {
		return '<form method="post" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '">'
			. wp_nonce_field( 'ga_azione', '_wpnonce', true, false )
			. '<input type="hidden" name="action" value="ga_azione"><input type="hidden" name="azione" value="' . esc_attr( $azione ) . '">'
			. $contenuto . '<p><button type="submit" class="button ' . esc_attr( $classe ) . '">' . esc_html( $pulsante ) . '</button></p></form>';
	}

	public static function pagina(): void {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$avviso = get_transient( 'ga_avviso_' . get_current_user_id() );
		delete_transient( 'ga_avviso_' . get_current_user_id() );
		$s = GA_Connettore::stato();
		echo '<div class="wrap"><h1>' . esc_html__( 'Gestione Associazione', 'gestione-associazione' ) . '</h1>';
		if ( $avviso ) {
			echo '<div class="notice notice-' . esc_attr( $avviso[0] ) . '"><p>' . esc_html( $avviso[1] ) . '</p></div>';
		}
		$errore = get_option( 'ga_ultimo_errore' );
		if ( $errore ) {
			echo '<div class="notice notice-warning"><p>' . esc_html( sprintf( __( 'Ultimo aggiornamento non riuscito (%1$s): %2$s', 'gestione-associazione' ), wp_date( 'd/m/Y H:i', $errore['quando'] ), $errore['errore'] ) ) . '</p></div>';
		}

		echo '<h2>' . esc_html__( 'Collegamento al gestionale', 'gestione-associazione' ) . '</h2>';
		if ( GA_Connettore::abbinato() ) {
			echo '<table class="form-table"><tr><th>' . esc_html__( 'Gestionale', 'gestione-associazione' ) . '</th><td>' . esc_html( ( $s['nome_istanza'] ?? '' ) . ' – ' . $s['indirizzo'] ) . '</td></tr>';
			echo '<tr><th>' . esc_html__( 'Impronta', 'gestione-associazione' ) . '</th><td><code>' . esc_html( GA_Connettore::impronta() ) . '</code><p class="description">' . esc_html__( 'Deve coincidere con quella mostrata dal gestionale (Sistema → Collegamenti), da confrontare per telefono o di persona prima di attivare il collegamento.', 'gestione-associazione' ) . '</p></td></tr>';
			echo '<tr><th>' . esc_html__( 'Abbinato il', 'gestione-associazione' ) . '</th><td>' . esc_html( wp_date( 'd/m/Y H:i', (int) $s['abbinato_il'] ) ) . '</td></tr></table>';
			echo self::modulo( 'prova', '', __( 'Prova il collegamento', 'gestione-associazione' ), 'button-secondary' );
			echo self::modulo( 'aggiorna', '', __( 'Aggiorna ora eventi e organigramma', 'gestione-associazione' ), 'button-secondary' );
		} else {
			echo '<p>' . esc_html__( 'Nel gestionale, in Sistema → Collegamenti, l\'amministratore crea un invito per un\'«integrazione esterna» con gli ambiti necessari (domande, contatti, eventi e adesioni, organigramma, verifica tessere) e vi comunica l\'indirizzo e il codice, valido 24 ore.', 'gestione-associazione' ) . '</p>';
			echo self::modulo( 'abbina',
				'<table class="form-table"><tr><th><label for="ga-indirizzo">' . esc_html__( 'Indirizzo del gestionale', 'gestione-associazione' ) . '</label></th><td><input id="ga-indirizzo" class="regular-text" type="url" name="indirizzo" placeholder="https://gestionale.example.org" required></td></tr>'
				. '<tr><th><label for="ga-invito">' . esc_html__( 'Codice d\'invito', 'gestione-associazione' ) . '</label></th><td><input id="ga-invito" class="regular-text" name="invito" required autocomplete="off"></td></tr>'
				. '<tr><th><label for="ga-nome">' . esc_html__( 'Nome di questo sito', 'gestione-associazione' ) . '</label></th><td><input id="ga-nome" class="regular-text" name="nome" value="' . esc_attr( get_bloginfo( 'name' ) ) . '"></td></tr></table>',
				__( 'Abbina', 'gestione-associazione' ) );
		}

		$opz = GA_Eventi::impostazioni();
		echo '<h2>' . esc_html__( 'Eventi sul sito', 'gestione-associazione' ) . '</h2>';
		echo '<p>' . esc_html__( 'Gli eventi segnati nel gestionale «pubblica sui siti collegati» diventano eventi del calendario del sito (consigliato) o articoli. Data, luogo, posti e adesione restano sempre quelli del gestionale; il testo e le foto che aggiungete non vengono toccati.', 'gestione-associazione' ) . '</p>';
		if ( class_exists( 'Tribe__Events__Main' ) && 'calendario' === $opz['modo'] && 'eventi' === $opz['slug_archivio'] ) {
			echo '<div class="notice notice-warning inline"><p>' . esc_html__( 'The Events Calendar è attivo e usa già l\'indirizzo /eventi/: scegliete un altro indirizzo per il calendario (es. «calendario») oppure disattivate The Events Calendar.', 'gestione-associazione' ) . '</p></div>';
		}
		$autori = wp_dropdown_users( array( 'name' => 'autore', 'selected' => (int) $opz['autore'], 'echo' => false, 'capability' => 'edit_posts', 'show_option_none' => __( '— nessuno —', 'gestione-associazione' ), 'option_none_value' => 0 ) );
		echo self::modulo( 'articoli',
			'<table class="form-table"><tr><th>' . esc_html__( 'Modalità', 'gestione-associazione' ) . '</th><td><select name="modo">'
			. '<option value="calendario"' . selected( $opz['modo'], 'calendario', false ) . '>' . esc_html__( 'Calendario degli eventi del sito (consigliato)', 'gestione-associazione' ) . '</option>'
			. '<option value="articoli"' . selected( $opz['modo'], 'articoli', false ) . '>' . esc_html__( 'Articoli del blog', 'gestione-associazione' ) . '</option>'
			. '<option value="nessuno"' . selected( $opz['modo'], 'nessuno', false ) . '>' . esc_html__( 'Nessuno (solo shortcode e blocchi)', 'gestione-associazione' ) . '</option></select></td></tr>'
			. '<tr><th>' . esc_html__( 'Indirizzi del calendario', 'gestione-associazione' ) . '</th><td>' . esc_html( home_url( '/' ) ) . '<input name="slug_archivio" value="' . esc_attr( $opz['slug_archivio'] ) . '" class="small-text">/ · ' . esc_html( home_url( '/' ) ) . '<input name="slug_evento" value="' . esc_attr( $opz['slug_evento'] ) . '" class="small-text">/…'
			. ( 'calendario' === $opz['modo'] && get_post_type_archive_link( GA_Calendario::TIPO ) ? '<p class="description"><a href="' . esc_url( get_post_type_archive_link( GA_Calendario::TIPO ) ) . '">' . esc_html__( 'Apri il calendario', 'gestione-associazione' ) . '</a></p>' : '' ) . '</td></tr>'
			. '<tr><th>' . esc_html__( 'Stato', 'gestione-associazione' ) . '</th><td><select name="stato"><option value="draft"' . selected( $opz['stato'], 'draft', false ) . '>' . esc_html__( 'Bozza, da rivedere e pubblicare (consigliato)', 'gestione-associazione' ) . '</option><option value="publish"' . selected( $opz['stato'], 'publish', false ) . '>' . esc_html__( 'Pubblicato subito', 'gestione-associazione' ) . '</option></select></td></tr>'
			. '<tr><th>' . esc_html__( 'Categoria', 'gestione-associazione' ) . '</th><td><input name="categoria" value="' . esc_attr( $opz['categoria'] ) . '" class="regular-text"></td></tr>'
			. '<tr><th>' . esc_html__( 'Autore', 'gestione-associazione' ) . '</th><td>' . $autori . '</td></tr></table>',
			__( 'Salva', 'gestione-associazione' ), 'button-secondary' );

		$coda     = GA_Connettore::coda();
		$sospese  = array_filter( $coda, fn( $v ) => ! empty( $v['sospeso'] ) );
		$in_corso = count( $coda ) - count( $sospese );
		echo '<h2>' . esc_html__( 'Invii in coda', 'gestione-associazione' ) . '</h2>';
		if ( ! $coda ) {
			echo '<p>' . esc_html__( 'Nessun invio in attesa.', 'gestione-associazione' ) . '</p>';
		} else {
			echo '<p>' . esc_html__( 'I dati in coda sono cifrati per il gestionale: il sito non li può leggere.', 'gestione-associazione' ) . '</p>';
			if ( $in_corso ) {
				echo '<p>' . esc_html( sprintf( _n( '%d invio in attesa: si riprova da solo, a intervalli crescenti (fino a 6 ore) per 7 giorni.', '%d invii in attesa: si riprova da soli, a intervalli crescenti (fino a 6 ore) per 7 giorni.', $in_corso, 'gestione-associazione' ), $in_corso ) ) . '</p>';
			}
			echo '<table class="widefat striped"><thead><tr><th>' . esc_html__( 'Dal', 'gestione-associazione' ) . '</th><th>' . esc_html__( 'Tipo', 'gestione-associazione' ) . '</th><th>' . esc_html__( 'Tentativi', 'gestione-associazione' ) . '</th><th>' . esc_html__( 'Stato e ultimo errore', 'gestione-associazione' ) . '</th><th></th></tr></thead><tbody>';
			foreach ( $coda as $voce ) {
				$stato = ! empty( $voce['sospeso'] )
					? __( 'Non consegnato', 'gestione-associazione' )
					: sprintf( __( 'Prossimo tentativo: %s', 'gestione-associazione' ), wp_date( 'd/m/Y H:i', max( (int) ( $voce['prossimo'] ?? 0 ), time() ) ) );
				echo '<tr><td>' . esc_html( wp_date( 'd/m/Y H:i', (int) $voce['dal'] ) ) . '</td><td><code>' . esc_html( $voce['percorso'] ) . '</code></td><td>' . (int) $voce['tentativi'] . '</td>'
					. '<td>' . esc_html( $stato ) . '<br><small>' . esc_html( $voce['errore'] ?? '' ) . '</small></td><td>'
					. self::modulo( 'elimina_voce', '<input type="hidden" name="chiave" value="' . esc_attr( $voce['chiave'] ) . '">', __( 'Elimina', 'gestione-associazione' ), 'button-link-delete' )
					. '</td></tr>';
			}
			echo '</tbody></table>';
			if ( $sospese ) {
				echo '<div class="notice notice-error inline"><p>' . esc_html( sprintf( _n( '%d invio non consegnato: il gestionale lo ha rifiutato o non ha risposto per 7 giorni. Risolto il problema (collegamento attivo, orologio, dati), rimettetelo in coda; altrimenti eliminatelo.', '%d invii non consegnati: il gestionale li ha rifiutati o non ha risposto per 7 giorni. Risolto il problema (collegamento attivo, orologio, dati), rimetteteli in coda; altrimenti eliminateli.', count( $sospese ), 'gestione-associazione' ), count( $sospese ) ) ) . '</p></div>';
			}
			echo self::modulo( 'riprova_coda', '', __( 'Riprova ora tutti gli invii', 'gestione-associazione' ), 'button-secondary' );
		}

		$cache = get_option( GA_Eventi::CACHE, array() );
		echo '<h2>' . esc_html__( 'Sul sito', 'gestione-associazione' ) . '</h2><p>' . esc_html( sprintf( __( 'Eventi in cache: %1$d (letti il %2$s). Shortcode: [ga_domanda sezione="codice" statuto="url" informativa="url"], [ga_contatti], [ga_eventi], [ga_organigramma sezione="codice"], [ga_verifica_tessera]; gli stessi sono disponibili come blocchi.', 'gestione-associazione' ),
			count( $cache['eventi'] ?? array() ), isset( $cache['letto_il'] ) ? wp_date( 'd/m/Y H:i', $cache['letto_il'] ) : '-' ) ) . '</p>';

		if ( GA_Connettore::abbinato() ) {
			echo self::modulo( 'scollega', '', __( 'Togli il collegamento', 'gestione-associazione' ), 'button-link-delete' );
		}
		echo '</div>';
	}
}
