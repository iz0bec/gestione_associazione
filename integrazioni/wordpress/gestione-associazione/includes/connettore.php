<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Collegamento al gestionale tramite le API v1: abbinamento con invito monouso,
 *              chiavi del sito (cifrate nel database con le chiavi segrete di wp-config.php),
 *              richieste firmate, risposte verificate e decifrate, coda cifrata degli invii che
 *              non sono riusciti (una voce per invio, ripresa dal cron di WordPress con attesa
 *              crescente e senza doppioni; ciò che non si può consegnare resta «non consegnato»,
 *              visibile all'amministratore, mai scartato in silenzio).
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class GA_Errore_Connettore extends RuntimeException {

	public $stato;
	public $codice;

	public function __construct( string $messaggio, int $stato = 0, string $codice = '' ) {
		parent::__construct( $messaggio );
		$this->stato  = $stato;
		$this->codice = $codice;
	}
}

final class GA_Connettore {

	const OPZIONE = 'ga_connettore';
	const CODA_VECCHIA = 'ga_coda';      // 0.1.0: tutta la coda in una sola opzione
	const PREFISSO_CODA = 'ga_coda_';     // dalla 0.1.1: un'opzione per invio (ga_coda_<chiave>)
	const PREFISSO_BLOCCO = 'ga_blocco_';
	const VERSIONE_API = 'v1';
	const SCADENZA_CODA = 7 * DAY_IN_SECONDS;  // poi la voce resta, ma «non consegnata»
	const DURATA_SVUOTA = 600;                 // secondi massimi di un giro della coda

	/** Impostazioni del collegamento (mai la chiave privata in chiaro). */
	public static function stato(): array {
		$stato = get_option( self::OPZIONE, array() );
		return is_array( $stato ) ? $stato : array();
	}

	private static function salva( array $stato ): void {
		update_option( self::OPZIONE, $stato, false );
	}

	public static function abbinato(): bool {
		$s = self::stato();
		return ! empty( $s['istanza'] ) && ! empty( $s['jwks'] ) && ! empty( $s['indirizzo'] );
	}

	private static function materiale(): string {
		$parti = array();
		foreach ( array( 'AUTH_KEY', 'SECURE_AUTH_KEY', 'LOGGED_IN_KEY', 'NONCE_KEY' ) as $costante ) {
			$parti[] = defined( $costante ) ? constant( $costante ) : '';
		}
		return implode( '|', $parti ) . '|' . wp_salt( 'auth' );
	}

	/** Chiavi del sito: create alla prima necessità, conservate cifrate. */
	public static function chiavi(): array {
		$s = self::stato();
		if ( empty( $s['chiavi'] ) ) {
			$s['chiavi'] = GA_Cripto::sigilla( wp_json_encode( GA_Cripto::genera_chiavi() ), self::materiale() );
			$s['sito']   = wp_generate_uuid4();
			self::salva( $s );
		}
		return json_decode( GA_Cripto::apri( $s['chiavi'], self::materiale() ), true );
	}

	public static function nostro_jwks(): array {
		return GA_Cripto::jwks( self::chiavi() );
	}

	public static function impronta(): string {
		$s = self::stato();
		return empty( $s['jwks'] ) ? '' : GA_Cripto::impronta_abbinamento( self::nostro_jwks(), $s['jwks'] );
	}

	private static function chiave_istanza( string $uso ): array {
		foreach ( self::stato()['jwks']['keys'] ?? array() as $k ) {
			if ( ( $k['use'] ?? '' ) === $uso && ! isset( $k['exp'] ) ) {
				return $k;
			}
		}
		throw new GA_Errore_Connettore( __( 'Chiave del gestionale mancante: rifare l\'abbinamento.', 'gestione-associazione' ) );
	}

	// --- HTTP --------------------------------------------------------------------------------

	private static function http( string $metodo, string $url, array $intestazioni = array(), ?string $corpo = null ): array {
		$risposta = wp_remote_request( $url, array(
			'method'      => $metodo,
			'headers'     => $intestazioni + array( 'Accept' => 'application/json, application/jose' ),
			'body'        => $corpo,
			'timeout'     => 20,
			'redirection' => 0,
			'user-agent'  => 'GestioneAssociazione-WordPress/' . GA_VERSIONE,
		) );
		if ( is_wp_error( $risposta ) ) {
			throw new GA_Errore_Connettore( sprintf( __( 'Gestionale non raggiungibile: %s', 'gestione-associazione' ), $risposta->get_error_message() ) );
		}
		$intest = array();
		$tutte  = wp_remote_retrieve_headers( $risposta );
		$tutte  = is_object( $tutte ) && method_exists( $tutte, 'getAll' ) ? $tutte->getAll() : (array) $tutte;
		foreach ( $tutte as $nome => $valore ) {
			$intest[ strtolower( $nome ) ] = is_array( $valore ) ? implode( ', ', $valore ) : $valore;
		}
		return array( (int) wp_remote_retrieve_response_code( $risposta ), $intest, (string) wp_remote_retrieve_body( $risposta ) );
	}

	private static function errore_da( int $stato, array $intest, string $corpo ): GA_Errore_Connettore {
		$problema = json_decode( $corpo, true );
		$testo    = is_array( $problema ) ? ( $problema['detail'] ?? $problema['title'] ?? '' ) : '';
		$codice   = is_array( $problema ) ? (string) ( $problema['codice'] ?? '' ) : '';
		if ( '' === $testo ) {
			$testo = sprintf( __( 'Risposta inattesa del gestionale (%d).', 'gestione-associazione' ), $stato );
		}
		return new GA_Errore_Connettore( $testo, $stato, $codice );
	}

	/**
	 * Richiesta firmata al gestionale. $dati: array da inviare (cifrato se $cifra) o null.
	 * Restituisce [stato, dati decodificati (JSON o JWE decifrato), intestazioni].
	 */
	public static function richiesta( string $metodo, string $percorso, array $query = array(), ?array $dati = null,
		bool $cifra = false, string $idempotenza = '', ?string $jwe_pronto = null ): array {
		if ( ! self::abbinato() ) {
			throw new GA_Errore_Connettore( __( 'Il sito non è ancora collegato al gestionale.', 'gestione-associazione' ) );
		}
		$s       = self::stato();
		$chiavi  = self::chiavi();
		$ns      = self::nostro_jwks();
		$path    = '/api/' . self::VERSIONE_API . $percorso;
		$qs      = http_build_query( $query, '', '&', PHP_QUERY_RFC3986 );
		$corpo   = null;
		$intest  = array();
		if ( null !== $jwe_pronto ) {
			$corpo                  = $jwe_pronto;
			$intest['Content-Type'] = 'application/jose';
		} elseif ( null !== $dati ) {
			$json = wp_json_encode( $dati, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
			if ( $cifra ) {
				$corpo                  = GA_Cripto::cifra( $json, self::chiave_istanza( 'enc' ) );
				$intest['Content-Type'] = 'application/jose';
			} else {
				$corpo                  = $json;
				$intest['Content-Type'] = 'application/json';
			}
		}
		if ( '' !== $idempotenza ) {
			$intest['Idempotency-Key'] = $idempotenza;
		}
		$firme  = GA_Firma::firma_richiesta( $metodo, $path, $qs, $s['istanza'], $corpo, $ns['keys'][0]['kid'], $chiavi['firma'] );
		$intest = $intest + $firme;
		$url    = rtrim( $s['indirizzo'], '/' ) . $path . ( '' === $qs ? '' : '?' . $qs );
		list( $stato, $risp, $testo ) = self::http( $metodo, $url, $intest, $corpo );
		$membro = GA_Firma::membri( $firme['Signature'] )['ga'];
		try {
			GA_Firma::verifica_risposta( $stato, $risp, $testo, $membro, $s['jwks'] );
		} catch ( GA_Errore_Firma $e ) {
			throw new GA_Errore_Connettore( sprintf( __( 'Risposta del gestionale non verificata: %s', 'gestione-associazione' ), $e->getMessage() ), $stato, 'non-verificata' );
		}
		if ( $stato >= 400 ) {
			throw self::errore_da( $stato, $risp, $testo );
		}
		$tipo = strtolower( strtok( $risp['content-type'] ?? '', ';' ) );
		if ( 'application/jose' === $tipo ) {
			$testo = GA_Cripto::decifra( $testo, $chiavi['cifratura'] );
		}
		$decodificato = '' === $testo ? null : json_decode( $testo, true );
		return array( $stato, $decodificato, $risp );
	}

	// --- abbinamento -----------------------------------------------------------------------------

	/** Abbinamento con l'invito creato nel gestionale (Sistema → Collegamenti). */
	public static function abbina( string $indirizzo, string $codice, string $nome ): array {
		$indirizzo = untrailingslashit( esc_url_raw( trim( $indirizzo ) ) );
		if ( ! preg_match( '#^https://#', $indirizzo ) ) {
			throw new GA_Errore_Connettore( __( 'Indicare l\'indirizzo https del gestionale.', 'gestione-associazione' ) );
		}
		list( $stato, , $testo ) = self::http( 'GET', $indirizzo . '/.well-known/gestione-associazione' );
		$istanza = json_decode( $testo, true );
		if ( 200 !== $stato || empty( $istanza['istanza'] ) || ! in_array( self::VERSIONE_API, $istanza['versioni_api'] ?? array(), true ) ) {
			throw new GA_Errore_Connettore( __( 'All\'indirizzo indicato non risponde un gestionale compatibile (API v1).', 'gestione-associazione' ) );
		}
		$chiavi = self::chiavi();
		$ns     = self::nostro_jwks();
		$s      = self::stato();
		$corpo  = wp_json_encode( array(
			'istanza' => $s['sito'],
			'nome'    => $nome,
			'tipo'    => 'integrazione',
			'jwks'    => $ns,
		), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES );
		$path   = '/api/' . self::VERSIONE_API . '/abbinamenti';
		$firme  = GA_Firma::firma_richiesta( 'POST', $path, '', $istanza['istanza'], $corpo, $ns['keys'][0]['kid'], $chiavi['firma'] );
		list( $stato, $risp, $testo ) = self::http( 'POST', $indirizzo . $path,
			array( 'Content-Type' => 'application/json', 'Invito' => trim( $codice ) ) + $firme, $corpo );
		if ( 201 !== $stato ) {
			throw self::errore_da( $stato, $risp, $testo );
		}
		$esito = json_decode( $testo, true );
		$s['indirizzo']     = $indirizzo;
		$s['istanza']       = $istanza['istanza'];
		$s['nome_istanza']  = $istanza['nome'] ?? '';
		$s['jwks']          = $esito['jwks'];
		$s['abbinato_il']   = time();
		$s['impronta_gest'] = $esito['impronta'] ?? '';
		self::salva( $s );
		try {  // la firma della risposta si verifica ora che conosciamo le chiavi
			GA_Firma::verifica_risposta( $stato, $risp, $testo, GA_Firma::membri( $firme['Signature'] )['ga'], $esito['jwks'] );
		} catch ( GA_Errore_Firma $e ) {
			self::scollega();
			throw new GA_Errore_Connettore( __( 'La risposta all\'abbinamento non è firmata dal gestionale: abbinamento annullato.', 'gestione-associazione' ) );
		}
		if ( ! empty( $esito['impronta'] ) && $esito['impronta'] !== self::impronta() ) {
			self::scollega();
			throw new GA_Errore_Connettore( __( 'Le impronte non coincidono: abbinamento annullato.', 'gestione-associazione' ) );
		}
		return $esito;
	}

	/** Diagnosi del collegamento (firma, orologio, stato e ambiti della controparte). */
	public static function prova(): array {
		list( , $diagnosi ) = self::richiesta( 'POST', '/prova' );
		return is_array( $diagnosi ) ? $diagnosi : array();
	}

	public static function scollega(): void {
		$s = self::stato();
		foreach ( array( 'indirizzo', 'istanza', 'nome_istanza', 'jwks', 'abbinato_il', 'impronta_gest' ) as $k ) {
			unset( $s[ $k ] );
		}
		self::salva( $s );
	}

	// --- blocchi fra processi -----------------------------------------------------------------

	/**
	 * Blocco atomico fra processi (cron, amministrazione): INSERT IGNORE sulla chiave unica di
	 * option_name, letto e tolto senza la cache delle opzioni. Scade da solo dopo $durata secondi.
	 */
	public static function blocca( string $nome, int $durata ): bool {
		global $wpdb;
		$opzione = self::PREFISSO_BLOCCO . $nome;
		for ( $giro = 0; $giro < 2; $giro++ ) {
			$preso = $wpdb->query( $wpdb->prepare(
				"INSERT IGNORE INTO {$wpdb->options} (option_name, option_value, autoload) VALUES (%s, %s, 'no')",
				$opzione, (string) ( time() + $durata )
			) );
			if ( $preso ) {
				return true;
			}
			$scade = (int) $wpdb->get_var( $wpdb->prepare( "SELECT option_value FROM {$wpdb->options} WHERE option_name = %s", $opzione ) );
			if ( $scade >= time() ) {
				return false;
			}
			$wpdb->query( $wpdb->prepare( "DELETE FROM {$wpdb->options} WHERE option_name = %s AND option_value = %s", $opzione, (string) $scade ) );
		}
		return false;
	}

	public static function sblocca( string $nome ): void {
		global $wpdb;
		$wpdb->delete( $wpdb->options, array( 'option_name' => self::PREFISSO_BLOCCO . $nome ) );
	}

	// --- invii con coda -------------------------------------------------------------------------

	/**
	 * Errore da ritentare: gestionale irraggiungibile o in errore, risposta non verificabile
	 * (es. una pagina d'errore del proxy), collegamento sospeso o non ancora attivo, orologio
	 * sfasato, richiesta gemella in corso, troppe richieste. Gli altri 4xx sono un rifiuto dei dati.
	 */
	public static function ritentabile( GA_Errore_Connettore $e ): bool {
		return 0 === $e->stato || $e->stato >= 500 || 'non-verificata' === $e->codice
			|| in_array( $e->stato, array( 401, 403, 408, 409, 425, 429 ), true );
	}

	private static function attesa( int $tentativi ): int {
		return (int) min( 15 * MINUTE_IN_SECONDS * ( 2 ** min( max( $tentativi - 1, 0 ), 5 ) ), 6 * HOUR_IN_SECONDS );
	}

	/**
	 * Invia dati personali (domanda, contatto, adesione): cifrati subito per il gestionale. Se il
	 * gestionale non li può ricevere ora, il JWE resta in coda (illeggibile per il sito) e si riprova.
	 * Restituisce [stato, risposta] oppure [0, null] se messo in coda.
	 */
	public static function invia( string $percorso, array $dati ): array {
		$idempotenza = wp_generate_uuid4();
		$jwe         = GA_Cripto::cifra( wp_json_encode( $dati, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ), self::chiave_istanza( 'enc' ) );
		try {
			list( $stato, $risposta ) = self::richiesta( 'POST', $percorso, array(), null, true, $idempotenza, $jwe );
			return array( $stato, $risposta );
		} catch ( GA_Errore_Connettore $e ) {
			if ( ! self::ritentabile( $e ) ) {
				throw $e;  // dati non validi o operazione rifiutata: lo dice la persona, non si ritenta
			}
			// un'opzione per invio: l'aggiunta non riscrive le altre voci (niente aggiornamenti persi)
			add_option( self::PREFISSO_CODA . $idempotenza, array(
				'percorso'  => $percorso,
				'jwe'       => $jwe,
				'chiave'    => $idempotenza,
				'tentativi' => 1,
				'dal'       => time(),
				'prossimo'  => time() + self::attesa( 1 ),
				'errore'    => $e->getMessage(),
				'sospeso'   => false,
			), '', 'no' );
			return array( 0, null );
		}
	}

	/** Voci della coda [nome opzione => voce], in ordine di arrivo. */
	public static function coda(): array {
		global $wpdb;
		self::migra_coda();
		$nomi = $wpdb->get_col( $wpdb->prepare( "SELECT option_name FROM {$wpdb->options} WHERE option_name LIKE %s ORDER BY option_id",
			$wpdb->esc_like( self::PREFISSO_CODA ) . '%' ) );
		$voci = array();
		foreach ( $nomi as $nome ) {
			$voce = get_option( $nome );
			if ( is_array( $voce ) && ! empty( $voce['jwe'] ) ) {
				$voci[ $nome ] = $voce;
			}
		}
		return $voci;
	}

	/** Porta la coda della 0.1.0 (una sola opzione) a una voce per invio. */
	private static function migra_coda(): void {
		$vecchia = get_option( self::CODA_VECCHIA, null );
		if ( null === $vecchia ) {
			return;
		}
		foreach ( is_array( $vecchia ) ? $vecchia : array() as $voce ) {
			if ( is_array( $voce ) && ! empty( $voce['jwe'] ) && ! empty( $voce['chiave'] ) ) {
				add_option( self::PREFISSO_CODA . $voce['chiave'], $voce + array( 'prossimo' => 0, 'sospeso' => false ), '', 'no' );
			}
		}
		delete_option( self::CODA_VECCHIA );
	}

	/** Riprova gli invii in coda (cron di WordPress); un solo giro per volta. */
	public static function svuota_coda(): int {
		if ( ! self::abbinato() ) {
			return 0;
		}
		if ( ! self::coda() || ! self::blocca( 'coda', self::DURATA_SVUOTA + 60 ) ) {
			return 0;
		}
		$inizio = time();
		$fatti  = 0;
		try {
			foreach ( self::coda() as $nome => $voce ) {  // riletta sotto il blocco
				if ( time() - $inizio > self::DURATA_SVUOTA ) {
					break;  // il resto al prossimo giro, prima che il blocco scada
				}
				if ( ! empty( $voce['sospeso'] ) || (int) ( $voce['prossimo'] ?? 0 ) > time() ) {
					continue;
				}
				try {
					self::richiesta( 'POST', $voce['percorso'], array(), null, true, $voce['chiave'], $voce['jwe'] );
					delete_option( $nome );
					$fatti++;
				} catch ( GA_Errore_Connettore $e ) {
					$voce['tentativi'] = (int) $voce['tentativi'] + 1;
					$voce['errore']    = $e->getMessage();
					if ( ! self::ritentabile( $e ) || time() - (int) $voce['dal'] > self::SCADENZA_CODA ) {
						$voce['sospeso'] = true;  // resta, visibile nelle impostazioni: mai scartato
					} else {
						$voce['prossimo'] = time() + self::attesa( $voce['tentativi'] );
					}
					update_option( $nome, $voce, false );
				}
			}
		} finally {
			self::sblocca( 'coda' );
		}
		return $fatti;
	}

	/** Rimette in coda le voci non consegnate (dopo aver risolto il problema). */
	public static function riprova_coda(): int {
		if ( ! self::blocca( 'coda', 60 ) ) {
			throw new GA_Errore_Connettore( __( 'La coda è in lavorazione: riprovare fra qualche minuto.', 'gestione-associazione' ) );
		}
		$n = 0;
		try {
			foreach ( self::coda() as $nome => $voce ) {
				if ( ! empty( $voce['sospeso'] ) || (int) ( $voce['prossimo'] ?? 0 ) > time() ) {
					$voce['sospeso']  = false;
					$voce['prossimo'] = 0;
					$voce['dal']      = time();
					update_option( $nome, $voce, false );
					$n++;
				}
			}
		} finally {
			self::sblocca( 'coda' );
		}
		return $n;
	}

	/** Elimina una voce della coda (decisione dell'amministratore: i dati non arriveranno). */
	public static function elimina_voce( string $chiave ): bool {
		if ( ! preg_match( '/^[0-9a-f-]{36}$/', $chiave ) ) {
			return false;
		}
		if ( ! self::blocca( 'coda', 60 ) ) {  // non mentre un giro della coda la sta riscrivendo
			throw new GA_Errore_Connettore( __( 'La coda è in lavorazione: riprovare fra qualche minuto.', 'gestione-associazione' ) );
		}
		try {
			return delete_option( self::PREFISSO_CODA . $chiave );
		} finally {
			self::sblocca( 'coda' );
		}
	}

	/** Lettura pubblica (eventi, organigramma, tessere): firmata, non cifrata. */
	public static function leggi( string $percorso, array $query = array() ) {
		list( , $dati ) = self::richiesta( 'GET', $percorso, $query );
		return $dati;
	}
}
