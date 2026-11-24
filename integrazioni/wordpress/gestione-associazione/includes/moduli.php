<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Moduli sul sito (shortcode e blocchi): domanda di iscrizione, modulo contatti,
 *              eventi con adesione, organigramma, verifica della tessera. I dati personali
 *              partono subito cifrati verso il gestionale e non restano nel sito; anti-spam con
 *              campo nascosto e tempo minimo di compilazione, senza servizi esterni; il gettone
 *              col tempo si rinnova al caricamento della pagina (REST), così regge la cache di pagina.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class GA_Moduli {

	const SECONDI_MINIMI = 4;
	const ORE_MASSIME    = 3;
	const MODULI         = array( 'domanda', 'contatti', 'adesione' );

	/** Esito dell'invio in corso (stessa richiesta: i campi restano compilati se c'è un errore). */
	private static $esito = array();

	public static function avvia(): void {
		foreach ( array( 'domanda', 'contatti', 'eventi', 'organigramma', 'verifica_tessera' ) as $nome ) {
			add_shortcode( 'ga_' . $nome, array( __CLASS__, 'mostra_' . $nome ) );
		}
		add_action( 'init', array( __CLASS__, 'ricevi' ) );
		add_action( 'wp_enqueue_scripts', function () {
			wp_register_style( 'gestione-associazione', GA_URL . 'assets/stile.css', array(), GA_VERSIONE );
			wp_register_script( 'gestione-associazione-moduli', GA_URL . 'assets/moduli.js', array(), GA_VERSIONE, true );
		} );
		add_action( 'rest_api_init', function () {
			register_rest_route( 'gestione-associazione/v1', '/gettone', array(
				'methods'             => 'GET',
				'permission_callback' => '__return_true',
				'args'                => array( 'modulo' => array( 'required' => true, 'type' => 'string', 'enum' => self::MODULI ) ),
				'callback'            => function ( WP_REST_Request $richiesta ) {
					$risposta = new WP_REST_Response( array( 't' => self::gettone( $richiesta['modulo'] ) ) );
					$risposta->header( 'Cache-Control', 'no-store, max-age=0' );
					return $risposta;
				},
			) );
		} );
	}

	// --- anti-spam -----------------------------------------------------------------------------

	/** Ora di presentazione del modulo, firmata: «ora|firma». */
	private static function gettone( string $modulo ): string {
		$t = time();
		return $t . '|' . wp_hash( $modulo . '|' . $t, 'nonce' );
	}

	private static function campi_controllo( string $modulo ): string {
		return '<input type="hidden" name="ga_modulo" value="' . esc_attr( $modulo ) . '">'
			. '<input type="hidden" name="ga_t" value="' . esc_attr( self::gettone( $modulo ) ) . '">'
			. '<p class="ga-nascosto" aria-hidden="true"><label>' . esc_html__( 'Lasciare vuoto', 'gestione-associazione' )
			. ' <input type="text" name="ga_sito_web" value="" tabindex="-1" autocomplete="off"></label></p>';
	}

	private static function controlla_spam( string $modulo ): ?string {
		if ( ! empty( $_POST['ga_sito_web'] ) ) {
			return __( 'Invio non accettato.', 'gestione-associazione' );
		}
		$parti = explode( '|', sanitize_text_field( wp_unslash( $_POST['ga_t'] ?? '' ) ) );
		if ( count( $parti ) !== 2 || ! hash_equals( wp_hash( $modulo . '|' . $parti[0], 'nonce' ), $parti[1] ) ) {
			return __( 'Modulo scaduto: ricaricare la pagina e riprovare.', 'gestione-associazione' );
		}
		$trascorsi = time() - (int) $parti[0];
		if ( $trascorsi < self::SECONDI_MINIMI ) {
			return __( 'Invio troppo rapido: controllare i dati e riprovare.', 'gestione-associazione' );
		}
		if ( $trascorsi > self::ORE_MASSIME * HOUR_IN_SECONDS ) {
			return __( 'Modulo scaduto: ricaricare la pagina e riprovare.', 'gestione-associazione' );
		}
		return null;
	}

	private static function campo( string $nome, int $massimo = 200 ): string {
		$valore = sanitize_textarea_field( wp_unslash( $_POST[ $nome ] ?? '' ) );
		return mb_substr( trim( $valore ), 0, $massimo );
	}

	private static function valore( string $nome ): string {
		return esc_attr( isset( $_POST[ $nome ] ) ? sanitize_text_field( wp_unslash( $_POST[ $nome ] ) ) : '' );
	}

	// --- ricezione degli invii ------------------------------------------------------------------

	public static function ricevi(): void {
		if ( 'POST' !== ( $_SERVER['REQUEST_METHOD'] ?? '' ) || empty( $_POST['ga_modulo'] ) ) {
			return;
		}
		$modulo = sanitize_key( wp_unslash( $_POST['ga_modulo'] ) );
		$errore = self::controlla_spam( $modulo );
		if ( $errore ) {
			self::$esito[ $modulo ] = array( 'errore' => $errore );
			return;
		}
		try {
			switch ( $modulo ) {
				case 'domanda':
					$esito = self::invia_domanda();
					break;
				case 'contatti':
					$esito = self::invia_contatto();
					break;
				case 'adesione':
					$esito = self::invia_adesione();
					break;
				default:
					return;
			}
		} catch ( GA_Errore_Connettore $e ) {
			$esito = array( 'errore' => $e->getMessage() );
		} catch ( Throwable $e ) {
			$esito = array( 'errore' => __( 'Invio non riuscito: riprovare più tardi.', 'gestione-associazione' ) );
		}
		self::$esito[ $modulo ] = $esito;
	}

	private static function esito_invio( array $risultato, string $ok ): array {
		if ( 0 === $risultato[0] ) {
			return array( 'ok' => __( 'Ricevuto. Il gestionale ora non può riceverlo: il messaggio è conservato cifrato e verrà consegnato appena possibile.', 'gestione-associazione' ) );
		}
		return array( 'ok' => $ok );
	}

	private static function invia_domanda(): array {
		if ( empty( $_POST['accetta_statuto'] ) || empty( $_POST['consenso_trattamento'] ) ) {
			return array( 'errore' => __( 'Per inviare la domanda servono l\'accettazione dello statuto e il consenso al trattamento dei dati.', 'gestione-associazione' ) );
		}
		$dati = array(
			'cognome'              => self::campo( 'cognome', 100 ),
			'nome'                 => self::campo( 'nome', 100 ),
			'codice_fiscale'       => strtoupper( self::campo( 'codice_fiscale', 16 ) ),
			'data_nascita'         => self::campo( 'data_nascita', 10 ),
			'luogo_nascita'        => self::campo( 'luogo_nascita', 100 ),
			'email'                => sanitize_email( wp_unslash( $_POST['email'] ?? '' ) ),
			'telefono'             => self::campo( 'telefono', 30 ),
			'cellulare'            => self::campo( 'cellulare', 30 ),
			'indirizzo'            => self::campo( 'indirizzo', 255 ),
			'cap'                  => self::campo( 'cap', 5 ),
			'comune'               => self::campo( 'comune', 100 ),
			'provincia'            => strtoupper( self::campo( 'provincia', 2 ) ),
			'motivazione'          => self::campo( 'motivazione', 2000 ),
			'accetta_statuto'      => true,
			'consenso_trattamento' => true,
			'consenso_immagini'    => ! empty( $_POST['consenso_immagini'] ),
			'prestato_il'          => gmdate( 'Y-m-d\TH:i:s\Z' ),
		);
		foreach ( array( 'sezione', 'tipologia' ) as $facoltativo ) {
			$valore = self::campo( 'ga_' . $facoltativo, 100 );
			if ( '' !== $valore ) {
				$dati[ $facoltativo ] = $valore;
			}
		}
		$dati = array_filter( $dati, fn( $v ) => '' !== $v );
		return self::esito_invio( GA_Connettore::invia( '/domande', $dati ),
			__( 'Domanda inviata. La esaminerà il consiglio direttivo; riceverete una risposta all\'indirizzo indicato.', 'gestione-associazione' ) );
	}

	private static function invia_contatto(): array {
		$dati = array_filter( array(
			'nome'     => self::campo( 'nome', 200 ),
			'email'    => sanitize_email( wp_unslash( $_POST['email'] ?? '' ) ),
			'telefono' => self::campo( 'telefono', 30 ),
			'oggetto'  => self::campo( 'oggetto', 200 ),
			'testo'    => self::campo( 'testo', 10000 ),
		), fn( $v ) => '' !== $v );
		if ( empty( $dati['nome'] ) || empty( $dati['email'] ) || empty( $dati['testo'] ) ) {
			return array( 'errore' => __( 'Nome, email e messaggio sono obbligatori.', 'gestione-associazione' ) );
		}
		return self::esito_invio( GA_Connettore::invia( '/contatti', $dati ), __( 'Messaggio inviato. Grazie!', 'gestione-associazione' ) );
	}

	private static function invia_adesione(): array {
		$evento = sanitize_text_field( wp_unslash( $_POST['ga_evento'] ?? '' ) );
		if ( ! preg_match( '/^[0-9a-f-]{36}$/', $evento ) ) {
			return array( 'errore' => __( 'Evento non valido.', 'gestione-associazione' ) );
		}
		$dati = array_filter( array(
			'cognome'        => self::campo( 'cognome', 100 ),
			'nome'           => self::campo( 'nome', 100 ),
			'email'          => sanitize_email( wp_unslash( $_POST['email'] ?? '' ) ),
			'telefono'       => self::campo( 'telefono', 30 ),
			'accompagnatori' => max( 0, (int) ( $_POST['accompagnatori'] ?? 0 ) ),
			'note'           => self::campo( 'note', 255 ),
		), fn( $v ) => '' !== $v );
		if ( empty( $dati['cognome'] ) ) {
			return array( 'errore' => __( 'Il cognome è obbligatorio.', 'gestione-associazione' ), 'evento' => $evento );
		}
		$risultato = GA_Connettore::invia( '/eventi/' . $evento . '/adesioni', $dati );
		$esito     = self::esito_invio( $risultato, __( 'Adesione registrata. Grazie!', 'gestione-associazione' ) );
		if ( 0 !== $risultato[0] ) {
			try {
				GA_Eventi::aggiorna_cache();  // posti liberi aggiornati
			} catch ( Throwable $e ) {
				// l'adesione è registrata: i posti si aggiornano al prossimo giro del cron
			}
		}
		return $esito + array( 'evento' => $evento );
	}

	// --- presentazione --------------------------------------------------------------------------

	private static function avviso( string $modulo ): string {
		$e = self::$esito[ $modulo ] ?? array();
		if ( isset( $e['ok'] ) ) {
			return '<div class="ga-avviso ga-ok" role="status">' . esc_html( $e['ok'] ) . '</div>';
		}
		if ( isset( $e['errore'] ) ) {
			return '<div class="ga-avviso ga-errore" role="alert">' . esc_html( $e['errore'] ) . '</div>';
		}
		return '';
	}

	private static function non_collegato(): string {
		return current_user_can( 'manage_options' )
			? '<div class="ga-avviso ga-errore">' . esc_html__( 'Gestione Associazione: il sito non è collegato al gestionale (Impostazioni → Gestione Associazione).', 'gestione-associazione' ) . '</div>'
			: '';
	}

	private static function input( string $nome, string $etichetta, string $tipo = 'text', bool $obbligatorio = false, string $extra = '' ): string {
		return '<p><label for="ga-' . esc_attr( $nome ) . '">' . esc_html( $etichetta ) . ( $obbligatorio ? ' *' : '' ) . '</label>'
			. '<input id="ga-' . esc_attr( $nome ) . '" type="' . esc_attr( $tipo ) . '" name="' . esc_attr( $nome ) . '" value="' . self::valore( $nome ) . '"'
			. ( $obbligatorio ? ' required' : '' ) . ' ' . $extra . '></p>';
	}

	private static function inizio_modulo( string $modulo, string $classe ): string {
		wp_enqueue_style( 'gestione-associazione' );
		wp_enqueue_script( 'gestione-associazione-moduli' );
		return '<form class="ga-modulo ' . esc_attr( $classe ) . '" method="post" action="" data-ga-gettone="'
			. esc_url( rest_url( 'gestione-associazione/v1/gettone' ) ) . '">' . self::campi_controllo( $modulo );
	}

	public static function mostra_domanda( $attributi = array() ): string {
		if ( ! GA_Connettore::abbinato() ) {
			return self::non_collegato();
		}
		$a = shortcode_atts( array( 'sezione' => '', 'tipologia' => '', 'statuto' => '', 'informativa' => '' ), $attributi );
		if ( isset( self::$esito['domanda']['ok'] ) ) {
			return self::avviso( 'domanda' );
		}
		$statuto     = $a['statuto'] ? '<a href="' . esc_url( $a['statuto'] ) . '" target="_blank" rel="noopener">' . esc_html__( 'lo statuto', 'gestione-associazione' ) . '</a>' : esc_html__( 'lo statuto', 'gestione-associazione' );
		$informativa = $a['informativa'] ? '<a href="' . esc_url( $a['informativa'] ) . '" target="_blank" rel="noopener">' . esc_html__( 'l\'informativa', 'gestione-associazione' ) . '</a>' : esc_html__( 'l\'informativa', 'gestione-associazione' );
		$h  = self::avviso( 'domanda' ) . self::inizio_modulo( 'domanda', 'ga-domanda' );
		$h .= '<input type="hidden" name="ga_sezione" value="' . esc_attr( $a['sezione'] ) . '"><input type="hidden" name="ga_tipologia" value="' . esc_attr( $a['tipologia'] ) . '">';
		$h .= '<fieldset><legend>' . esc_html__( 'Dati anagrafici', 'gestione-associazione' ) . '</legend>';
		$h .= self::input( 'cognome', __( 'Cognome', 'gestione-associazione' ), 'text', true, 'maxlength="100" autocomplete="family-name"' );
		$h .= self::input( 'nome', __( 'Nome', 'gestione-associazione' ), 'text', true, 'maxlength="100" autocomplete="given-name"' );
		$h .= self::input( 'codice_fiscale', __( 'Codice fiscale', 'gestione-associazione' ), 'text', true, 'maxlength="16" minlength="16" pattern="[A-Za-z0-9]{16}"' );
		$h .= self::input( 'data_nascita', __( 'Data di nascita', 'gestione-associazione' ), 'date', true );
		$h .= self::input( 'luogo_nascita', __( 'Luogo di nascita', 'gestione-associazione' ), 'text', true, 'maxlength="100"' );
		$h .= '</fieldset><fieldset><legend>' . esc_html__( 'Residenza e recapiti', 'gestione-associazione' ) . '</legend>';
		$h .= self::input( 'indirizzo', __( 'Indirizzo', 'gestione-associazione' ), 'text', true, 'maxlength="255" autocomplete="street-address"' );
		$h .= self::input( 'cap', __( 'CAP', 'gestione-associazione' ), 'text', true, 'maxlength="5" pattern="[0-9]{5}" autocomplete="postal-code"' );
		$h .= self::input( 'comune', __( 'Comune', 'gestione-associazione' ), 'text', true, 'maxlength="100" autocomplete="address-level2"' );
		$h .= self::input( 'provincia', __( 'Provincia (sigla)', 'gestione-associazione' ), 'text', true, 'maxlength="2" pattern="[A-Za-z]{2}"' );
		$h .= self::input( 'email', __( 'Email', 'gestione-associazione' ), 'email', false, 'autocomplete="email"' );
		$h .= self::input( 'cellulare', __( 'Cellulare', 'gestione-associazione' ), 'tel', false, 'maxlength="30" autocomplete="tel"' );
		$h .= self::input( 'telefono', __( 'Altro telefono', 'gestione-associazione' ), 'tel', false, 'maxlength="30"' );
		$h .= '</fieldset><p><label for="ga-motivazione">' . esc_html__( 'Perché chiedete di iscrivervi (facoltativo)', 'gestione-associazione' ) . '</label><textarea id="ga-motivazione" name="motivazione" rows="3" maxlength="2000">' . esc_textarea( self::campo( 'motivazione', 2000 ) ) . '</textarea></p>';
		$h .= '<p><label><input type="checkbox" name="accetta_statuto" value="1" required> ' . sprintf( esc_html__( 'Dichiaro di accettare %s *', 'gestione-associazione' ), $statuto ) . '</label></p>';
		$h .= '<p><label><input type="checkbox" name="consenso_trattamento" value="1" required> ' . sprintf( esc_html__( 'Ho letto %s e acconsento al trattamento dei dati per l\'iscrizione *', 'gestione-associazione' ), $informativa ) . '</label></p>';
		$h .= '<p><label><input type="checkbox" name="consenso_immagini" value="1"> ' . esc_html__( 'Acconsento all\'uso di foto e video delle attività (facoltativo)', 'gestione-associazione' ) . '</label></p>';
		$h .= '<p class="ga-nota">' . esc_html__( 'I dati vanno direttamente, cifrati, al gestionale dell\'associazione: il sito non li conserva. La domanda è esaminata dal consiglio direttivo.', 'gestione-associazione' ) . '</p>';
		return $h . '<p><button type="submit">' . esc_html__( 'Invia la domanda', 'gestione-associazione' ) . '</button></p></form>';
	}

	public static function mostra_contatti( $attributi = array() ): string {
		if ( ! GA_Connettore::abbinato() ) {
			return self::non_collegato();
		}
		if ( isset( self::$esito['contatti']['ok'] ) ) {
			return self::avviso( 'contatti' );
		}
		$h  = self::avviso( 'contatti' ) . self::inizio_modulo( 'contatti', 'ga-contatti' );
		$h .= self::input( 'nome', __( 'Nome e cognome', 'gestione-associazione' ), 'text', true, 'maxlength="200" autocomplete="name"' );
		$h .= self::input( 'email', __( 'Email', 'gestione-associazione' ), 'email', true, 'autocomplete="email"' );
		$h .= self::input( 'telefono', __( 'Telefono (facoltativo)', 'gestione-associazione' ), 'tel', false, 'maxlength="30"' );
		$h .= self::input( 'oggetto', __( 'Oggetto', 'gestione-associazione' ), 'text', false, 'maxlength="200"' );
		$h .= '<p><label for="ga-testo">' . esc_html__( 'Messaggio', 'gestione-associazione' ) . ' *</label><textarea id="ga-testo" name="testo" rows="6" maxlength="10000" required>' . esc_textarea( self::campo( 'testo', 10000 ) ) . '</textarea></p>';
		$h .= '<p class="ga-nota">' . esc_html__( 'Il messaggio arriva, cifrato, alla segreteria dell\'associazione.', 'gestione-associazione' ) . '</p>';
		return $h . '<p><button type="submit">' . esc_html__( 'Invia', 'gestione-associazione' ) . '</button></p></form>';
	}

	private static function data( ?string $iso, string $formato = 'j F Y, H:i' ): string {
		return $iso ? wp_date( $formato, strtotime( $iso ) ) : '';
	}

	public static function mostra_eventi( $attributi = array() ): string {
		$a       = shortcode_atts( array( 'quanti' => 20, 'uuid' => '' ), $attributi );
		$eventi  = GA_Eventi::elenco();
		if ( '' !== $a['uuid'] ) {  // un solo evento (es. nell'articolo creato dal connettore)
			$eventi = array_values( array_filter( $eventi, fn( $e ) => $e['uuid'] === $a['uuid'] ) );
		}
		$eventi  = array_slice( $eventi, 0, max( 1, (int) $a['quanti'] ) );
		if ( ! $eventi ) {
			if ( '' !== $a['uuid'] ) {  // articolo di un evento passato o non più pubblico
				return '<p class="ga-vuoto">' . esc_html__( 'L\'evento non è più in programma.', 'gestione-associazione' ) . '</p>';
			}
			return '<p class="ga-vuoto">' . esc_html__( 'Nessun evento in programma.', 'gestione-associazione' ) . '</p>';
		}
		wp_enqueue_style( 'gestione-associazione' );
		$aperto = self::$esito['adesione']['evento'] ?? '';
		$h      = '<div class="ga-eventi">';
		foreach ( $eventi as $e ) {
			$h .= '<article class="ga-evento' . ( $e['annullato'] ? ' ga-annullato' : '' ) . '" id="ga-evento-' . esc_attr( $e['uuid'] ) . '">';
			$h .= '<h3>' . ( $e['annullato'] ? esc_html__( 'ANNULLATO – ', 'gestione-associazione' ) : '' ) . esc_html( $e['titolo'] ) . '</h3>';
			$h .= '<p class="ga-quando">' . esc_html( self::data( $e['inizio'] ) ) . ( $e['luogo'] ? ' · ' . esc_html( $e['luogo'] ) : '' ) . '</p>';
			if ( $e['descrizione'] ) {
				$h .= wpautop( esc_html( $e['descrizione'] ) );
			}
			if ( $e['quota'] ) {
				$h .= '<p>' . esc_html__( 'Quota:', 'gestione-associazione' ) . ' ' . esc_html( $e['quota'] ) . '</p>';
			}
			if ( null !== $e['posti_liberi'] ) {
				$h .= '<p class="ga-posti">' . esc_html( sprintf( _n( '%d posto disponibile', '%d posti disponibili', (int) $e['posti_liberi'], 'gestione-associazione' ), (int) $e['posti_liberi'] ) ) . '</p>';
			}
			if ( ! $e['annullato'] && $e['adesioni_aperte'] && ( null === $e['posti_liberi'] || $e['posti_liberi'] > 0 ) ) {
				$h .= ( $aperto === $e['uuid'] ? self::avviso( 'adesione' ) : '' );
				if ( ! ( $aperto === $e['uuid'] && isset( self::$esito['adesione']['ok'] ) ) ) {
					$h .= '<details' . ( $aperto === $e['uuid'] ? ' open' : '' ) . '><summary>' . esc_html__( 'Aderisci', 'gestione-associazione' ) . '</summary>';
					$h .= self::inizio_modulo( 'adesione', 'ga-adesione' ) . '<input type="hidden" name="ga_evento" value="' . esc_attr( $e['uuid'] ) . '">';
					$h .= self::input( 'cognome', __( 'Cognome', 'gestione-associazione' ), 'text', true, 'maxlength="100"' );
					$h .= self::input( 'nome', __( 'Nome', 'gestione-associazione' ), 'text', false, 'maxlength="100"' );
					$h .= self::input( 'email', __( 'Email', 'gestione-associazione' ), 'email' );
					$h .= self::input( 'telefono', __( 'Telefono', 'gestione-associazione' ), 'tel', false, 'maxlength="30"' );
					if ( $e['accompagnatori_max'] > 0 ) {
						$h .= self::input( 'accompagnatori', __( 'Accompagnatori', 'gestione-associazione' ), 'number', false, 'min="0" max="' . (int) $e['accompagnatori_max'] . '"' );
					}
					$h .= self::input( 'note', __( 'Note', 'gestione-associazione' ), 'text', false, 'maxlength="255"' );
					$h .= '<p><button type="submit">' . esc_html__( 'Conferma l\'adesione', 'gestione-associazione' ) . '</button></p></form></details>';
				}
			} elseif ( ! $e['annullato'] ) {
				$h .= '<p class="ga-nota">' . esc_html__( 'Adesioni chiuse.', 'gestione-associazione' ) . '</p>';
			}
			$h .= '</article>';
		}
		return $h . '</div>';
	}

	public static function mostra_organigramma( $attributi = array() ): string {
		$a      = shortcode_atts( array( 'sezione' => '' ), $attributi );
		$organi = GA_Eventi::organigramma();
		$h      = '';
		foreach ( $organi as $o ) {
			if ( (string) ( $o['sezione'] ?? '' ) !== (string) $a['sezione'] || empty( $o['componenti'] ) ) {
				continue;
			}
			$h .= '<section class="ga-organo"><h3>' . esc_html( $o['organo'] ) . '</h3><ul>';
			foreach ( $o['componenti'] as $c ) {
				$h .= '<li><span class="ga-ruolo">' . esc_html( $c['ruolo_descrizione'] ?? $c['ruolo'] ) . '</span> ' . esc_html( $c['nome'] ) . '</li>';
			}
			$h .= '</ul></section>';
		}
		if ( '' === $h ) {
			return '<p class="ga-vuoto">' . esc_html__( 'Organigramma non disponibile.', 'gestione-associazione' ) . '</p>';
		}
		wp_enqueue_style( 'gestione-associazione' );
		return '<div class="ga-organigramma">' . $h . '</div>';
	}

	public static function mostra_verifica_tessera( $attributi = array() ): string {
		wp_enqueue_style( 'gestione-associazione' );
		$codice = isset( $_GET['ga_tessera'] ) ? sanitize_text_field( wp_unslash( $_GET['ga_tessera'] ) ) : '';
		$h      = '<form class="ga-modulo ga-verifica" method="get" action=""><p><label for="ga-tessera">' . esc_html__( 'Codice della tessera (dal QR della tessera digitale)', 'gestione-associazione' ) . '</label>'
			. '<input id="ga-tessera" name="ga_tessera" value="' . esc_attr( $codice ) . '" maxlength="64" required> <button type="submit">' . esc_html__( 'Verifica', 'gestione-associazione' ) . '</button></p></form>';
		if ( '' === $codice || ! GA_Connettore::abbinato() ) {
			return $h;
		}
		$ip    = sanitize_text_field( $_SERVER['REMOTE_ADDR'] ?? '' );
		$conto = 'ga_verifiche_' . md5( $ip );
		$fatte = (int) get_transient( $conto );
		if ( $fatte >= 10 ) {
			return $h . '<div class="ga-avviso ga-errore">' . esc_html__( 'Troppe verifiche: riprovare fra un minuto.', 'gestione-associazione' ) . '</div>';
		}
		set_transient( $conto, $fatte + 1, MINUTE_IN_SECONDS );
		try {
			$esito = GA_Connettore::leggi( '/tessere/' . rawurlencode( $codice ) );
		} catch ( GA_Errore_Connettore $e ) {
			$esito = 404 === $e->stato ? array( 'valida' => false, 'motivo' => __( 'Tessera non trovata.', 'gestione-associazione' ) ) : null;
		}
		if ( ! is_array( $esito ) ) {
			return $h . '<div class="ga-avviso ga-errore">' . esc_html__( 'Verifica non disponibile in questo momento.', 'gestione-associazione' ) . '</div>';
		}
		$testo = ! empty( $esito['valida'] )
			? sprintf( __( 'Tessera valida per il %1$d%2$s.', 'gestione-associazione' ), (int) ( $esito['anno'] ?? 0 ), ! empty( $esito['sezione'] ) ? ' – ' . $esito['sezione'] : '' )
			: ( $esito['motivo'] ?? __( 'Tessera non valida.', 'gestione-associazione' ) );
		return $h . '<div class="ga-avviso ' . ( ! empty( $esito['valida'] ) ? 'ga-ok' : 'ga-errore' ) . '" role="status">' . esc_html( $testo ) . '</div>';
	}
}
