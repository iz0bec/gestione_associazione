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
					self::torna( 'success', sprintf( __( '%1$d eventi letti; articoli: %2$d creati, %3$d aggiornati; invii in coda consegnati: %4$d.', 'gestione-associazione' ), count( $eventi ), $creati, $aggiornati, $inviati ) );
					break;
				case 'articoli':
					update_option( 'ga_articoli', array(
						'attivi'    => ! empty( $_POST['attivi'] ),
						'stato'     => 'publish' === ( $_POST['stato'] ?? '' ) ? 'publish' : 'draft',
						'categoria' => sanitize_text_field( wp_unslash( $_POST['categoria'] ?? '' ) ),
						'autore'    => (int) ( $_POST['autore'] ?? 0 ),
					), false );
					self::torna( 'success', __( 'Impostazioni degli articoli salvate.', 'gestione-associazione' ) );
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
			echo self::modulo( 'aggiorna', '', __( 'Aggiorna ora eventi, organigramma e articoli', 'gestione-associazione' ), 'button-secondary' );
		} else {
			echo '<p>' . esc_html__( 'Nel gestionale, in Sistema → Collegamenti, l\'amministratore crea un invito per un\'«integrazione esterna» con gli ambiti necessari (domande, contatti, eventi e adesioni, organigramma, verifica tessere) e vi comunica l\'indirizzo e il codice, valido 24 ore.', 'gestione-associazione' ) . '</p>';
			echo self::modulo( 'abbina',
				'<table class="form-table"><tr><th><label for="ga-indirizzo">' . esc_html__( 'Indirizzo del gestionale', 'gestione-associazione' ) . '</label></th><td><input id="ga-indirizzo" class="regular-text" type="url" name="indirizzo" placeholder="https://gestionale.example.org" required></td></tr>'
				. '<tr><th><label for="ga-invito">' . esc_html__( 'Codice d\'invito', 'gestione-associazione' ) . '</label></th><td><input id="ga-invito" class="regular-text" name="invito" required autocomplete="off"></td></tr>'
				. '<tr><th><label for="ga-nome">' . esc_html__( 'Nome di questo sito', 'gestione-associazione' ) . '</label></th><td><input id="ga-nome" class="regular-text" name="nome" value="' . esc_attr( get_bloginfo( 'name' ) ) . '"></td></tr></table>',
				__( 'Abbina', 'gestione-associazione' ) );
		}

		$opz = GA_Eventi::impostazioni();
		echo '<h2>' . esc_html__( 'Articoli degli eventi', 'gestione-associazione' ) . '</h2>';
		echo '<p>' . esc_html__( 'Per gli eventi segnati nel gestionale «pubblica sui siti collegati» il connettore crea un articolo, aggiornato quando l\'evento cambia; il testo che aggiungete nell\'articolo non viene toccato.', 'gestione-associazione' ) . '</p>';
		$autori = wp_dropdown_users( array( 'name' => 'autore', 'selected' => (int) $opz['autore'], 'echo' => false, 'capability' => 'edit_posts', 'show_option_none' => __( '— nessuno —', 'gestione-associazione' ), 'option_none_value' => 0 ) );
		echo self::modulo( 'articoli',
			'<table class="form-table"><tr><th>' . esc_html__( 'Articoli', 'gestione-associazione' ) . '</th><td><label><input type="checkbox" name="attivi" value="1"' . checked( $opz['attivi'], true, false ) . '> ' . esc_html__( 'Crea gli articoli degli eventi', 'gestione-associazione' ) . '</label></td></tr>'
			. '<tr><th>' . esc_html__( 'Stato', 'gestione-associazione' ) . '</th><td><select name="stato"><option value="draft"' . selected( $opz['stato'], 'draft', false ) . '>' . esc_html__( 'Bozza, da rivedere e pubblicare (consigliato)', 'gestione-associazione' ) . '</option><option value="publish"' . selected( $opz['stato'], 'publish', false ) . '>' . esc_html__( 'Pubblicato subito', 'gestione-associazione' ) . '</option></select></td></tr>'
			. '<tr><th>' . esc_html__( 'Categoria', 'gestione-associazione' ) . '</th><td><input name="categoria" value="' . esc_attr( $opz['categoria'] ) . '" class="regular-text"></td></tr>'
			. '<tr><th>' . esc_html__( 'Autore', 'gestione-associazione' ) . '</th><td>' . $autori . '</td></tr></table>',
			__( 'Salva', 'gestione-associazione' ), 'button-secondary' );

		$coda = get_option( GA_Connettore::CODA, array() );
		echo '<h2>' . esc_html__( 'Invii in coda', 'gestione-associazione' ) . '</h2><p>';
		echo $coda
			? esc_html( sprintf( _n( '%d invio in attesa (cifrato, illeggibile per il sito): si riprova ogni 15 minuti.', '%d invii in attesa (cifrati, illeggibili per il sito): si riprova ogni 15 minuti.', count( $coda ), 'gestione-associazione' ), count( $coda ) ) ) . ' ' . esc_html( end( $coda )['errore'] ?? '' )
			: esc_html__( 'Nessun invio in attesa.', 'gestione-associazione' );
		echo '</p>';

		$cache = get_option( GA_Eventi::CACHE, array() );
		echo '<h2>' . esc_html__( 'Sul sito', 'gestione-associazione' ) . '</h2><p>' . esc_html( sprintf( __( 'Eventi in cache: %1$d (letti il %2$s). Shortcode: [ga_domanda sezione="codice" statuto="url" informativa="url"], [ga_contatti], [ga_eventi], [ga_organigramma sezione="codice"], [ga_verifica_tessera]; gli stessi sono disponibili come blocchi.', 'gestione-associazione' ),
			count( $cache['eventi'] ?? array() ), isset( $cache['letto_il'] ) ? wp_date( 'd/m/Y H:i', $cache['letto_il'] ) : '-' ) ) . '</p>';

		if ( GA_Connettore::abbinato() ) {
			echo self::modulo( 'scollega', '', __( 'Togli il collegamento', 'gestione-associazione' ), 'button-link-delete' );
		}
		echo '</div>';
	}
}
