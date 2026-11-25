<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Gestore degli eventi del connettore, senza plugin di calendario esterni: tipo di
 *              contenuto «Evento» (archivio e pagina dell'evento), viste elenco, mese e giorno,
 *              prossimi eventi, iCal (feed e singolo evento), dati strutturati schema.org/Event.
 *              Data, luogo, posti e adesione arrivano dal gestionale; testo e foto restano del
 *              redattore. Gli eventi passati restano in archivio, gli annullati sono segnalati.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class GA_Calendario {

	const TIPO      = 'ga_evento';
	const TASSONOMIA = 'ga_evento_tipo';
	const CREATI    = 'ga_eventi_creati';  // [uuid => ID]: un evento cancellato dal redattore non torna
	const TIPI      = array(
		'cerimonia'  => 'Cerimonia o commemorazione',
		'incontro'   => 'Incontro o conferenza',
		'gita'       => 'Gita o viaggio',
		'conviviale' => 'Pranzo o cena',
		'altro'      => 'Altro',
	);

	public static function avvia(): void {
		add_action( 'init', array( __CLASS__, 'registra' ) );
		add_filter( 'the_content', array( __CLASS__, 'contenuto' ), 20 );
		add_filter( 'template_include', array( __CLASS__, 'modello_archivio' ) );
		add_action( 'pre_get_posts', array( __CLASS__, 'ordina_archivio' ) );
		add_action( 'template_redirect', array( __CLASS__, 'ical' ) );
		add_action( 'wp_head', array( __CLASS__, 'dati_strutturati' ) );
		foreach ( array( 'calendario', 'prossimi_eventi' ) as $nome ) {
			add_shortcode( 'ga_' . $nome, array( __CLASS__, 'mostra_' . $nome ) );
		}
	}

	public static function attivo(): bool {
		return 'calendario' === GA_Eventi::impostazioni()['modo'];
	}

	// --- registrazione ---------------------------------------------------------------------------

	public static function registra(): void {
		if ( ! self::attivo() ) {
			return;
		}
		$opz = GA_Eventi::impostazioni();
		register_post_type( self::TIPO, array(
			'labels'        => array(
				'name'          => __( 'Eventi', 'gestione-associazione' ),
				'singular_name' => __( 'Evento', 'gestione-associazione' ),
				'edit_item'     => __( 'Modifica evento', 'gestione-associazione' ),
				'all_items'     => __( 'Tutti gli eventi', 'gestione-associazione' ),
				'menu_name'     => __( 'Eventi', 'gestione-associazione' ),
			),
			'public'        => true,
			'show_in_rest'  => true,
			'menu_icon'     => 'dashicons-calendar-alt',
			'supports'      => array( 'title', 'editor', 'thumbnail', 'excerpt' ),
			'has_archive'   => $opz['slug_archivio'],
			'rewrite'       => array( 'slug' => $opz['slug_evento'], 'with_front' => false ),
			// gli eventi nascono dal gestionale: dal sito si rivedono, non si creano
			'capabilities'  => array( 'create_posts' => 'do_not_allow' ),
			'map_meta_cap'  => true,
		) );
		register_taxonomy( self::TASSONOMIA, self::TIPO, array(
			'label'        => __( 'Tipi di evento', 'gestione-associazione' ),
			'public'       => true,
			'show_in_rest' => true,
			'rewrite'      => array( 'slug' => $opz['slug_archivio'] . '/tipo' ),
		) );
		if ( get_option( 'ga_calendario_flush' ) ) {  // slug cambiati: si rigenerano le regole
			flush_rewrite_rules( false );
			delete_option( 'ga_calendario_flush' );
		}
	}

	// --- sincronizzazione dal gestionale -----------------------------------------------------------

	private static function evento_di( string $uuid ): ?WP_Post {
		$trovati = get_posts( array(
			'post_type'   => self::TIPO,
			'post_status' => array( 'publish', 'draft', 'pending', 'future', 'private', 'trash' ),
			'meta_key'    => GA_Eventi::META,
			'meta_value'  => $uuid,
			'numberposts' => 1,
		) );
		return $trovati ? $trovati[0] : null;
	}

	private static function meta( array $e ): array {
		return array(
			GA_Eventi::META          => $e['uuid'],
			GA_Eventi::META_VERSIONE => (int) $e['versione'],
			'_ga_inizio'             => (string) $e['inizio'],
			'_ga_inizio_ts'          => (int) strtotime( (string) $e['inizio'] ),
			'_ga_fine'               => (string) ( $e['fine'] ?? '' ),
			'_ga_luogo'              => (string) $e['luogo'],
			'_ga_quota'              => (string) $e['quota'],
			'_ga_annullato'          => $e['annullato'] ? 1 : 0,
		);
	}

	private static function titolo( array $e ): string {
		$titolo = wp_strip_all_tags( (string) $e['titolo'] );
		return $e['annullato'] ? __( 'ANNULLATO', 'gestione-associazione' ) . ' – ' . $titolo : $titolo;
	}

	/** Crea o aggiorna gli eventi segnati «pubblica sui siti collegati». [creati, aggiornati] */
	public static function sincronizza( array $opz ): array {
		$prima    = get_option( self::CREATI, array() );
		$prima    = is_array( $prima ) ? $prima : array();
		$registro = $prima;
		$creati   = 0;
		$aggiornati = 0;
		foreach ( GA_Eventi::elenco() as $e ) {
			if ( empty( $e['sito'] ) ) {
				continue;
			}
			$post = self::evento_di( $e['uuid'] );
			if ( null !== $post ) {
				$registro[ $e['uuid'] ] = $post->ID;
				if ( 'trash' === $post->post_status ) {
					continue;
				}
			} elseif ( isset( $registro[ $e['uuid'] ] ) ) {
				continue;  // eliminato dal redattore: non si ricrea
			}
			if ( null === $post ) {
				$id = wp_insert_post( array(
					'post_type'    => self::TIPO,
					'post_status'  => in_array( $opz['stato'], array( 'draft', 'publish', 'pending' ), true ) ? $opz['stato'] : 'draft',
					'post_title'   => self::titolo( $e ),
					'post_excerpt' => wp_trim_words( (string) $e['descrizione'], 40 ),
					'post_content' => $e['descrizione'] ? wpautop( esc_html( $e['descrizione'] ) ) : '',
					'post_author'  => (int) $opz['autore'],
					'meta_input'   => self::meta( $e ),
				), true );
				if ( is_wp_error( $id ) ) {
					continue;
				}
				$registro[ $e['uuid'] ] = (int) $id;
				self::imposta_tipo( (int) $id, (string) ( $e['tipo'] ?? '' ) );
				$creati++;
				do_action( 'ga_evento_sincronizzato', (int) $id, $e, 'creato' );
				continue;
			}
			if ( (int) get_post_meta( $post->ID, GA_Eventi::META_VERSIONE, true ) >= (int) $e['versione'] ) {
				continue;
			}
			GA_Eventi::aggiorna_titolo( $post->ID, self::titolo( $e ) );
			foreach ( self::meta( $e ) as $chiave => $valore ) {
				update_post_meta( $post->ID, $chiave, $valore );
			}
			self::imposta_tipo( $post->ID, (string) ( $e['tipo'] ?? '' ) );
			$aggiornati++;
			do_action( 'ga_evento_sincronizzato', $post->ID, $e, 'aggiornato' );
		}
		if ( $registro !== $prima ) {
			update_option( self::CREATI, $registro, false );
		}
		return array( $creati, $aggiornati );
	}

	private static function imposta_tipo( int $id, string $tipo ): void {
		if ( isset( self::TIPI[ $tipo ] ) ) {
			wp_set_object_terms( $id, __( self::TIPI[ $tipo ], 'gestione-associazione' ), self::TASSONOMIA ); // phpcs:ignore
		}
	}

	// --- dati di un evento -------------------------------------------------------------------------

	/** Dati per la presentazione: quelli correnti dalla cache, altrimenti quelli salvati. */
	public static function dati( int $id ): array {
		$uuid = (string) get_post_meta( $id, GA_Eventi::META, true );
		foreach ( GA_Eventi::elenco() as $e ) {
			if ( $e['uuid'] === $uuid ) {
				return $e + array( 'corrente' => true );
			}
		}
		return array(
			'uuid' => $uuid, 'titolo' => get_the_title( $id ), 'inizio' => get_post_meta( $id, '_ga_inizio', true ),
			'fine' => get_post_meta( $id, '_ga_fine', true ), 'luogo' => get_post_meta( $id, '_ga_luogo', true ),
			'quota' => get_post_meta( $id, '_ga_quota', true ), 'annullato' => (bool) get_post_meta( $id, '_ga_annullato', true ),
			'posti_liberi' => null, 'adesioni_aperte' => false, 'accompagnatori_max' => 0, 'descrizione' => '',
			'corrente' => false,
		);
	}

	private static function ora( string $iso, string $formato ): string {
		return $iso ? wp_date( $formato, strtotime( $iso ) ) : '';
	}

	private static function quando( array $e ): string {
		$testo = self::ora( (string) $e['inizio'], 'l j F Y, H:i' );
		if ( ! empty( $e['fine'] ) ) {
			$stesso = wp_date( 'Ymd', strtotime( $e['inizio'] ) ) === wp_date( 'Ymd', strtotime( $e['fine'] ) );
			$testo .= ' – ' . self::ora( (string) $e['fine'], $stesso ? 'H:i' : 'l j F Y, H:i' );
		}
		return $testo;
	}

	private static function utc( string $iso ): string {
		return gmdate( 'Ymd\THis\Z', strtotime( $iso ) );
	}

	private static function fine( array $e ): string {
		return ! empty( $e['fine'] ) ? (string) $e['fine'] : gmdate( 'c', strtotime( (string) $e['inizio'] ) + 2 * HOUR_IN_SECONDS );
	}

	// --- pagina dell'evento --------------------------------------------------------------------------

	public static function contenuto( $testo ) {
		if ( ! is_singular( self::TIPO ) || ! in_the_loop() || ! is_main_query() ) {
			return $testo;
		}
		wp_enqueue_style( 'gestione-associazione' );
		$id = get_the_ID();
		$e  = self::dati( $id );
		$h  = '<div class="ga-scheda-evento' . ( $e['annullato'] ? ' ga-annullato' : '' ) . '">';
		if ( $e['annullato'] ) {
			$h .= '<p class="ga-avviso ga-errore"><strong>' . esc_html__( 'Evento annullato.', 'gestione-associazione' ) . '</strong></p>';
		}
		$h .= '<dl>';
		$h .= '<dt>' . esc_html__( 'Quando', 'gestione-associazione' ) . '</dt><dd>' . esc_html( self::quando( $e ) ) . '</dd>';
		if ( $e['luogo'] ) {
			$mappa = 'https://www.openstreetmap.org/search?query=' . rawurlencode( (string) $e['luogo'] );
			$h    .= '<dt>' . esc_html__( 'Dove', 'gestione-associazione' ) . '</dt><dd>' . esc_html( $e['luogo'] )
				. ' · <a href="' . esc_url( $mappa ) . '" target="_blank" rel="noopener">' . esc_html__( 'mappa', 'gestione-associazione' ) . '</a></dd>';
		}
		$tipi = get_the_term_list( $id, self::TASSONOMIA, '', ', ' );
		if ( $tipi && ! is_wp_error( $tipi ) ) {
			$h .= '<dt>' . esc_html__( 'Tipo', 'gestione-associazione' ) . '</dt><dd>' . wp_kses_post( $tipi ) . '</dd>';
		}
		if ( $e['quota'] ) {
			$h .= '<dt>' . esc_html__( 'Quota', 'gestione-associazione' ) . '</dt><dd>' . esc_html( $e['quota'] ) . '</dd>';
		}
		if ( null !== $e['posti_liberi'] && ! $e['annullato'] ) {
			$h .= '<dt>' . esc_html__( 'Posti', 'gestione-associazione' ) . '</dt><dd>' . esc_html( sprintf( _n( '%d disponibile', '%d disponibili', (int) $e['posti_liberi'], 'gestione-associazione' ), (int) $e['posti_liberi'] ) ) . '</dd>';
		}
		$h .= '</dl>';
		if ( ! $e['annullato'] && $e['inizio'] ) {
			$google = add_query_arg( array(
				'action'   => 'TEMPLATE',
				'text'     => get_the_title( $id ),
				'dates'    => self::utc( (string) $e['inizio'] ) . '/' . self::utc( self::fine( $e ) ),
				'location' => (string) $e['luogo'],
				'details'  => get_permalink( $id ),
			), 'https://calendar.google.com/calendar/render' );
			$h .= '<p class="ga-aggiungi">' . esc_html__( 'Aggiungi al calendario:', 'gestione-associazione' )
				. ' <a href="' . esc_url( add_query_arg( 'ga_ical', $id, home_url( '/' ) ) ) . '">iCal</a>'
				. ' · <a href="' . esc_url( $google ) . '" target="_blank" rel="noopener">Google</a></p>';
		}
		$h .= '</div>';
		$adesione = ! empty( $e['corrente'] ) && GA_Connettore::abbinato() ? GA_Moduli::blocco_adesione( $e, true ) : '';
		if ( empty( $e['corrente'] ) && ! $e['annullato'] && strtotime( (string) $e['inizio'] ) < time() ) {
			$adesione = '<p class="ga-nota">' . esc_html__( 'Evento concluso.', 'gestione-associazione' ) . '</p>';
		}
		return $h . $testo . $adesione;
	}

	public static function dati_strutturati(): void {
		if ( ! is_singular( self::TIPO ) ) {
			return;
		}
		$id = get_queried_object_id();
		$e  = self::dati( $id );
		if ( ! $e['inizio'] ) {
			return;
		}
		$dati = array(
			'@context'            => 'https://schema.org',
			'@type'               => 'Event',
			'name'                => wp_strip_all_tags( get_the_title( $id ) ),
			'startDate'           => gmdate( 'c', strtotime( (string) $e['inizio'] ) ),
			'endDate'             => gmdate( 'c', strtotime( self::fine( $e ) ) ),
			'eventStatus'         => $e['annullato'] ? 'https://schema.org/EventCancelled' : 'https://schema.org/EventScheduled',
			'eventAttendanceMode' => 'https://schema.org/OfflineEventAttendanceMode',
			'description'         => wp_strip_all_tags( get_the_excerpt( $id ) ),
			'url'                 => get_permalink( $id ),
			'organizer'           => array( '@type' => 'Organization', 'name' => get_bloginfo( 'name' ), 'url' => home_url( '/' ) ),
		);
		if ( $e['luogo'] ) {
			$dati['location'] = array( '@type' => 'Place', 'name' => (string) $e['luogo'], 'address' => (string) $e['luogo'] );
		}
		if ( has_post_thumbnail( $id ) ) {
			$dati['image'] = get_the_post_thumbnail_url( $id, 'large' );
		}
		echo '<script type="application/ld+json">' . wp_json_encode( $dati, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) . "</script>\n";
	}

	// --- archivio e viste -----------------------------------------------------------------------------

	public static function ordina_archivio( WP_Query $q ): void {
		if ( is_admin() || ! $q->is_main_query() || ! ( $q->is_post_type_archive( self::TIPO ) || $q->is_tax( self::TASSONOMIA ) ) ) {
			return;
		}
		$q->set( 'meta_key', '_ga_inizio_ts' );
		$q->set( 'orderby', 'meta_value_num' );
		$q->set( 'order', 'ASC' );
	}

	/** Con un tema classico l'archivio mostra le viste del calendario dentro il tema. */
	public static function modello_archivio( $modello ) {
		if ( ( is_post_type_archive( self::TIPO ) || is_tax( self::TASSONOMIA ) ) && ! wp_is_block_theme() ) {
			return GA_DIR . 'templates/archivio-eventi.php';
		}
		return $modello;
	}

	private static function trova( array $argomenti ): array {
		return get_posts( array_merge( array(
			'post_type'   => self::TIPO,
			'post_status' => 'publish',
			'meta_key'    => '_ga_inizio_ts',
			'orderby'     => 'meta_value_num',
			'order'       => 'ASC',
			'numberposts' => 200,
		), $argomenti ) );
	}

	private static function tra( int $dal, int $al ): array {
		return self::trova( array( 'meta_query' => array( array(
			'key' => '_ga_inizio_ts', 'value' => array( $dal, $al ), 'compare' => 'BETWEEN', 'type' => 'NUMERIC',
		) ) ) );
	}

	private static function riga( WP_Post $p ): string {
		$inizio    = (int) get_post_meta( $p->ID, '_ga_inizio_ts', true );
		$annullato = (bool) get_post_meta( $p->ID, '_ga_annullato', true );
		$luogo     = (string) get_post_meta( $p->ID, '_ga_luogo', true );
		return '<li class="ga-cal-evento' . ( $annullato ? ' ga-annullato' : '' ) . '">'
			. '<span class="ga-cal-data"><span class="ga-cal-giorno">' . esc_html( wp_date( 'j', $inizio ) ) . '</span>'
			. '<span class="ga-cal-mese">' . esc_html( wp_date( 'M Y', $inizio ) ) . '</span></span>'
			. '<span class="ga-cal-testo"><a href="' . esc_url( get_permalink( $p ) ) . '">' . esc_html( get_the_title( $p ) ) . '</a>'
			. '<span class="ga-quando">' . esc_html( wp_date( 'l, H:i', $inizio ) ) . ( $luogo ? ' · ' . esc_html( $luogo ) : '' ) . '</span></span></li>';
	}

	private static function link_vista( string $vista, array $extra = array() ): string {
		$base = remove_query_arg( array( 'ga_vista', 'ga_mese', 'ga_giorno', 'ga_passati' ) );
		return esc_url( add_query_arg( array( 'ga_vista' => $vista ) + $extra, $base ) );
	}

	/** Viste del calendario: elenco (prossimi o passati), mese, giorno. */
	public static function vista( array $a = array() ): string {
		wp_enqueue_style( 'gestione-associazione' );
		$vista = sanitize_key( wp_unslash( $_GET['ga_vista'] ?? ( $a['vista'] ?? 'lista' ) ) );
		$vista = in_array( $vista, array( 'lista', 'mese', 'giorno' ), true ) ? $vista : 'lista';
		$adesso = current_time( 'timestamp', true );
		$h  = '<div class="ga-calendario"><nav class="ga-cal-viste">';
		foreach ( array( 'lista' => __( 'Elenco', 'gestione-associazione' ), 'mese' => __( 'Mese', 'gestione-associazione' ), 'giorno' => __( 'Giorno', 'gestione-associazione' ) ) as $chiave => $etichetta ) {
			$h .= '<a class="' . ( $vista === $chiave ? 'ga-attiva' : '' ) . '" href="' . self::link_vista( $chiave ) . '">' . esc_html( $etichetta ) . '</a> ';
		}
		$h .= '<a class="ga-cal-ical" href="' . esc_url( add_query_arg( 'ga_ical', 'tutti', home_url( '/' ) ) ) . '">' . esc_html__( 'Abbonati (iCal)', 'gestione-associazione' ) . '</a></nav>';
		if ( 'mese' === $vista ) {
			$h .= self::vista_mese( sanitize_text_field( wp_unslash( $_GET['ga_mese'] ?? '' ) ) );
		} elseif ( 'giorno' === $vista ) {
			$h .= self::vista_giorno( sanitize_text_field( wp_unslash( $_GET['ga_giorno'] ?? '' ) ) );
		} else {
			$passati = ! empty( $_GET['ga_passati'] );
			$eventi  = $passati
				? array_reverse( self::trova( array( 'meta_query' => array( array( 'key' => '_ga_inizio_ts', 'value' => $adesso, 'compare' => '<', 'type' => 'NUMERIC' ) ) ) ) )
				: self::trova( array( 'meta_query' => array( array( 'key' => '_ga_inizio_ts', 'value' => $adesso - 6 * HOUR_IN_SECONDS, 'compare' => '>=', 'type' => 'NUMERIC' ) ) ) );
			$eventi  = array_slice( $eventi, 0, max( 1, (int) ( $a['quanti'] ?? 50 ) ) );
			$h      .= $eventi ? '<ul class="ga-cal-elenco">' . implode( '', array_map( array( __CLASS__, 'riga' ), $eventi ) ) . '</ul>'
				: '<p class="ga-vuoto">' . esc_html( $passati ? __( 'Nessun evento passato.', 'gestione-associazione' ) : __( 'Nessun evento in programma.', 'gestione-associazione' ) ) . '</p>';
			$h      .= '<p class="ga-cal-nav"><a href="' . self::link_vista( 'lista', $passati ? array() : array( 'ga_passati' => 1 ) ) . '">'
				. esc_html( $passati ? __( 'Prossimi eventi', 'gestione-associazione' ) : __( 'Eventi passati', 'gestione-associazione' ) ) . '</a></p>';
		}
		return $h . '</div>';
	}

	private static function vista_mese( string $mese ): string {
		$fuso = wp_timezone();
		$primo = DateTimeImmutable::createFromFormat( '!Y-m', $mese, $fuso ) ?: new DateTimeImmutable( 'first day of this month 00:00', $fuso );
		$primo = $primo->modify( 'first day of this month' )->setTime( 0, 0 );
		$dopo  = $primo->modify( '+1 month' );
		$per_giorno = array();
		foreach ( self::tra( $primo->getTimestamp(), $dopo->getTimestamp() - 1 ) as $p ) {
			$per_giorno[ wp_date( 'j', (int) get_post_meta( $p->ID, '_ga_inizio_ts', true ) ) ][] = $p;
		}
		$h  = '<p class="ga-cal-nav"><a href="' . self::link_vista( 'mese', array( 'ga_mese' => $primo->modify( '-1 month' )->format( 'Y-m' ) ) ) . '">&larr;</a> '
			. '<strong>' . esc_html( wp_date( 'F Y', $primo->getTimestamp() ) ) . '</strong> '
			. '<a href="' . self::link_vista( 'mese', array( 'ga_mese' => $dopo->format( 'Y-m' ) ) ) . '">&rarr;</a></p>';
		$h .= '<table class="ga-cal-mese"><thead><tr>';
		foreach ( array( 'lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom' ) as $g ) {
			$h .= '<th>' . esc_html( $g ) . '</th>';
		}
		$h .= '</tr></thead><tbody><tr>';
		$vuote = (int) $primo->format( 'N' ) - 1;
		$h    .= str_repeat( '<td class="ga-vuota"></td>', $vuote );
		$giorni = (int) $primo->format( 't' );
		for ( $g = 1; $g <= $giorni; $g++ ) {
			if ( ( $vuote + $g - 1 ) % 7 === 0 && $g > 1 ) {
				$h .= '</tr><tr>';
			}
			$data = $primo->setDate( (int) $primo->format( 'Y' ), (int) $primo->format( 'n' ), $g );
			$h   .= '<td><a class="ga-cal-num" href="' . self::link_vista( 'giorno', array( 'ga_giorno' => $data->format( 'Y-m-d' ) ) ) . '">' . $g . '</a>';
			foreach ( $per_giorno[ (string) $g ] ?? array() as $p ) {
				$annullato = (bool) get_post_meta( $p->ID, '_ga_annullato', true );
				$h .= '<a class="ga-cal-voce' . ( $annullato ? ' ga-annullato' : '' ) . '" href="' . esc_url( get_permalink( $p ) ) . '">' . esc_html( get_the_title( $p ) ) . '</a>';
			}
			$h .= '</td>';
		}
		$resto = ( 7 - ( $vuote + $giorni ) % 7 ) % 7;
		return $h . str_repeat( '<td class="ga-vuota"></td>', $resto ) . '</tr></tbody></table>';
	}

	private static function vista_giorno( string $giorno ): string {
		$fuso   = wp_timezone();
		$data   = DateTimeImmutable::createFromFormat( '!Y-m-d', $giorno, $fuso ) ?: new DateTimeImmutable( 'today', $fuso );
		$eventi = self::tra( $data->getTimestamp(), $data->modify( '+1 day' )->getTimestamp() - 1 );
		$h      = '<p class="ga-cal-nav"><a href="' . self::link_vista( 'giorno', array( 'ga_giorno' => $data->modify( '-1 day' )->format( 'Y-m-d' ) ) ) . '">&larr;</a> '
			. '<strong>' . esc_html( wp_date( 'l j F Y', $data->getTimestamp() ) ) . '</strong> '
			. '<a href="' . self::link_vista( 'giorno', array( 'ga_giorno' => $data->modify( '+1 day' )->format( 'Y-m-d' ) ) ) . '">&rarr;</a></p>';
		return $h . ( $eventi ? '<ul class="ga-cal-elenco">' . implode( '', array_map( array( __CLASS__, 'riga' ), $eventi ) ) . '</ul>'
			: '<p class="ga-vuoto">' . esc_html__( 'Nessun evento in questo giorno.', 'gestione-associazione' ) . '</p>' );
	}

	public static function mostra_calendario( $attributi = array() ): string {
		if ( ! self::attivo() ) {
			return '';
		}
		return self::vista( shortcode_atts( array( 'vista' => 'lista', 'quanti' => 50 ), $attributi ) );
	}

	public static function mostra_prossimi_eventi( $attributi = array() ): string {
		if ( ! self::attivo() ) {
			return '';
		}
		wp_enqueue_style( 'gestione-associazione' );
		$a      = shortcode_atts( array( 'quanti' => 5 ), $attributi );
		$eventi = array_slice( self::trova( array( 'meta_query' => array( array(
			'key' => '_ga_inizio_ts', 'value' => time() - 6 * HOUR_IN_SECONDS, 'compare' => '>=', 'type' => 'NUMERIC',
		) ) ) ), 0, max( 1, (int) $a['quanti'] ) );
		if ( ! $eventi ) {
			return '<p class="ga-vuoto">' . esc_html__( 'Nessun evento in programma.', 'gestione-associazione' ) . '</p>';
		}
		$archivio = get_post_type_archive_link( self::TIPO );
		return '<div class="ga-calendario ga-prossimi"><ul class="ga-cal-elenco">' . implode( '', array_map( array( __CLASS__, 'riga' ), $eventi ) ) . '</ul>'
			. ( $archivio ? '<p class="ga-cal-nav"><a href="' . esc_url( $archivio ) . '">' . esc_html__( 'Tutti gli eventi', 'gestione-associazione' ) . '</a></p>' : '' ) . '</div>';
	}

	// --- iCal ------------------------------------------------------------------------------------------

	private static function ics_testo( string $s ): string {
		return str_replace( array( '\\', ';', ',', "\r\n", "\n" ), array( '\\\\', '\;', '\,', '\n', '\n' ), $s );
	}

	private static function ics_riga( string $riga ): string {
		$righe = array();
		while ( strlen( $riga ) > 75 ) {
			$taglio = 75;
			while ( $taglio > 0 && ( ord( $riga[ $taglio ] ) & 0xC0 ) === 0x80 ) {
				$taglio--;  // non spezzare un carattere UTF-8
			}
			$righe[] = substr( $riga, 0, $taglio );
			$riga    = ' ' . substr( $riga, $taglio );
		}
		$righe[] = $riga;
		return implode( "\r\n", $righe ) . "\r\n";
	}

	public static function ics( array $posts ): string {
		$host = wp_parse_url( home_url(), PHP_URL_HOST );
		$out  = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Gestione Associazione//Connettore WordPress//IT\r\nCALSCALE:GREGORIAN\r\n";
		$out .= self::ics_riga( 'X-WR-CALNAME:' . self::ics_testo( get_bloginfo( 'name' ) ) );
		foreach ( $posts as $p ) {
			$e = self::dati( $p->ID );
			if ( ! $e['inizio'] ) {
				continue;
			}
			$out .= "BEGIN:VEVENT\r\n";
			$out .= self::ics_riga( 'UID:' . ( $e['uuid'] ?: $p->ID ) . '@' . $host );
			$out .= 'DTSTAMP:' . gmdate( 'Ymd\THis\Z', strtotime( $p->post_modified_gmt . ' UTC' ) ) . "\r\n";
			$out .= 'DTSTART:' . self::utc( (string) $e['inizio'] ) . "\r\nDTEND:" . self::utc( self::fine( $e ) ) . "\r\n";
			$out .= self::ics_riga( 'SUMMARY:' . self::ics_testo( wp_strip_all_tags( get_the_title( $p ) ) ) );
			if ( $e['luogo'] ) {
				$out .= self::ics_riga( 'LOCATION:' . self::ics_testo( (string) $e['luogo'] ) );
			}
			$out .= self::ics_riga( 'DESCRIPTION:' . self::ics_testo( wp_strip_all_tags( get_the_excerpt( $p ) ) ) );
			$out .= self::ics_riga( 'URL:' . get_permalink( $p ) );
			$out .= 'STATUS:' . ( $e['annullato'] ? 'CANCELLED' : 'CONFIRMED' ) . "\r\nEND:VEVENT\r\n";
		}
		return $out . "END:VCALENDAR\r\n";
	}

	public static function ical(): void {
		if ( ! isset( $_GET['ga_ical'] ) || ! self::attivo() ) {
			return;
		}
		$richiesta = sanitize_key( wp_unslash( $_GET['ga_ical'] ) );
		if ( 'tutti' === $richiesta ) {
			$posts = self::trova( array( 'meta_query' => array( array(
				'key' => '_ga_inizio_ts', 'value' => time() - 90 * DAY_IN_SECONDS, 'compare' => '>=', 'type' => 'NUMERIC',
			) ) ) );
			$nome = 'eventi.ics';
		} else {
			$p = get_post( (int) $richiesta );
			if ( ! $p || self::TIPO !== $p->post_type || 'publish' !== $p->post_status ) {
				status_header( 404 );
				exit;
			}
			$posts = array( $p );
			$nome  = sanitize_title( $p->post_title ) . '.ics';
		}
		nocache_headers();
		header( 'Content-Type: text/calendar; charset=utf-8' );
		header( 'Content-Disposition: ' . ( 'tutti' === $richiesta ? 'inline' : 'attachment' ) . '; filename="' . $nome . '"' );
		echo self::ics( $posts ); // phpcs:ignore WordPress.Security.EscapeOutput -- testo iCal
		exit;
	}
}
