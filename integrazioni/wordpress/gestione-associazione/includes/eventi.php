<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Eventi e organigramma dal gestionale (solo dati pubblici, in cache e aggiornati dal
 *              cron) e articoli degli eventi da pubblicare sul sito: uno per evento, riconosciuto
 *              dal suo identificativo, in bozza per default, aggiornato quando l'evento cambia
 *              (titolo; data, luogo e adesioni sono sempre quelli correnti tramite lo shortcode),
 *              «ANNULLATO» nel titolo se l'evento è annullato, mai cancellato.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class GA_Eventi {

	const CACHE        = 'ga_eventi';
	const ORGANIGRAMMA = 'ga_organigramma';
	const META         = '_ga_evento';
	const META_VERSIONE = '_ga_evento_versione';

	public static function elenco(): array {
		$dati = get_option( self::CACHE, array() );
		return is_array( $dati['eventi'] ?? null ) ? $dati['eventi'] : array();
	}

	public static function organigramma(): array {
		$dati = get_option( self::ORGANIGRAMMA, array() );
		return is_array( $dati['organi'] ?? null ) ? $dati['organi'] : array();
	}

	/** Legge dal gestionale gli eventi da oggi in poi (tutte le pagine) e l'organigramma. */
	public static function aggiorna_cache(): array {
		if ( ! GA_Connettore::abbinato() ) {
			return array();
		}
		$eventi = array();
		$query  = array( 'dal' => wp_date( 'Y-m-d' ) );
		for ( $pagine = 0; $pagine < 20; $pagine++ ) {
			$pagina = GA_Connettore::leggi( '/eventi', $query );
			foreach ( $pagina['risultati'] ?? array() as $e ) {
				$eventi[] = array_intersect_key( $e, array_flip( array(
					'uuid', 'versione', 'titolo', 'tipo', 'inizio', 'fine', 'luogo', 'descrizione', 'quota', 'posti',
					'posti_liberi', 'accompagnatori_max', 'adesioni_aperte', 'chiusura_adesioni', 'pubblico', 'sito', 'annullato',
				) ) ) + array( 'sito' => false, 'posti_liberi' => null, 'accompagnatori_max' => 0, 'luogo' => '', 'descrizione' => '', 'quota' => '' );
			}
			if ( empty( $pagina['successivo'] ) ) {
				break;
			}
			$query['cursore'] = $pagina['successivo'];
		}
		usort( $eventi, fn( $a, $b ) => strcmp( $a['inizio'], $b['inizio'] ) );
		update_option( self::CACHE, array( 'eventi' => $eventi, 'letto_il' => time() ), false );
		try {
			$organi = GA_Connettore::leggi( '/organigramma' );
			update_option( self::ORGANIGRAMMA, array( 'organi' => is_array( $organi ) ? $organi : array(), 'letto_il' => time() ), false );
		} catch ( GA_Errore_Connettore $e ) {
			// organigramma non abilitato per questo collegamento: resta quello di prima
		}
		return $eventi;
	}

	// --- articoli degli eventi --------------------------------------------------------------

	public static function impostazioni(): array {
		return wp_parse_args( get_option( 'ga_articoli', array() ), array(
			'attivi'    => true,
			'stato'     => 'draft',
			'categoria' => __( 'Eventi', 'gestione-associazione' ),
			'autore'    => 0,
		) );
	}

	private static function articolo_di( string $uuid ): ?WP_Post {
		$trovati = get_posts( array(
			'post_type'   => 'post',
			'post_status' => array( 'publish', 'draft', 'pending', 'future', 'private' ),
			'meta_key'    => self::META,
			'meta_value'  => $uuid,
			'numberposts' => 1,
		) );
		return $trovati ? $trovati[0] : null;
	}

	private static function titolo( array $e ): string {
		$quando = wp_date( 'j F Y', strtotime( $e['inizio'] ) );
		$titolo = $e['titolo'] . ' – ' . $quando;
		return $e['annullato'] ? __( 'ANNULLATO', 'gestione-associazione' ) . ' – ' . $titolo : $titolo;
	}

	/**
	 * Crea o aggiorna gli articoli degli eventi segnati «pubblica sui siti collegati». Il testo
	 * scritto dal redattore non si tocca: il contenuto generato è solo lo shortcode dell'evento.
	 * Restituisce [creati, aggiornati].
	 */
	public static function sincronizza_articoli(): array {
		$opz = self::impostazioni();
		if ( empty( $opz['attivi'] ) ) {
			return array( 0, 0 );
		}
		$categoria = $opz['categoria'] ? (int) ( term_exists( $opz['categoria'], 'category' )['term_id'] ?? 0 ) : 0;
		if ( $opz['categoria'] && ! $categoria ) {
			$nuova     = wp_insert_term( $opz['categoria'], 'category' );
			$categoria = is_wp_error( $nuova ) ? 0 : (int) $nuova['term_id'];
		}
		$creati = 0;
		$aggiornati = 0;
		foreach ( self::elenco() as $e ) {
			if ( empty( $e['sito'] ) ) {
				continue;
			}
			$articolo = self::articolo_di( $e['uuid'] );
			if ( null === $articolo ) {
				$id = wp_insert_post( array(
					'post_type'    => 'post',
					'post_status'  => in_array( $opz['stato'], array( 'draft', 'publish', 'pending' ), true ) ? $opz['stato'] : 'draft',
					'post_title'   => self::titolo( $e ),
					'post_excerpt' => wp_trim_words( $e['descrizione'], 40 ),
					'post_content' => "<!-- wp:shortcode -->\n[ga_eventi uuid=\"" . $e['uuid'] . "\"]\n<!-- /wp:shortcode -->",
					'post_author'  => (int) $opz['autore'],
					'post_category' => $categoria ? array( $categoria ) : array(),
					'meta_input'   => array( self::META => $e['uuid'], self::META_VERSIONE => (int) $e['versione'] ),
				), true );
				if ( ! is_wp_error( $id ) ) {
					$creati++;
				}
				continue;
			}
			if ( (int) get_post_meta( $articolo->ID, self::META_VERSIONE, true ) >= (int) $e['versione'] ) {
				continue;
			}
			wp_update_post( array( 'ID' => $articolo->ID, 'post_title' => self::titolo( $e ) ) );
			update_post_meta( $articolo->ID, self::META_VERSIONE, (int) $e['versione'] );
			$aggiornati++;
		}
		return array( $creati, $aggiornati );
	}

	/** Lavoro periodico: coda degli invii, eventi, organigramma, articoli. */
	public static function periodico(): void {
		try {
			GA_Connettore::svuota_coda();
			self::aggiorna_cache();
			self::sincronizza_articoli();
			delete_option( 'ga_ultimo_errore' );
		} catch ( Throwable $e ) {
			update_option( 'ga_ultimo_errore', array( 'quando' => time(), 'errore' => $e->getMessage() ), false );
		}
	}
}
