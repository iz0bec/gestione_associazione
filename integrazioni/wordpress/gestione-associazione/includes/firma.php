<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Firma dei messaggi HTTP (RFC 9421, ed25519) e Content-Digest (RFC 9530) con il
 *              profilo del contratto: richieste su "@method" "@path" "@query"
 *              "destinatario-istanza" (e "content-digest"), risposte su "@status"
 *              "content-digest" "signature";req;key="ga". Nessuna funzione di WordPress.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) && PHP_SAPI !== 'cli' ) {
	exit;
}

class GA_Errore_Firma extends RuntimeException {}

final class GA_Firma {

	const ETICHETTA  = 'ga';
	const TAG        = 'ga-v1';
	const TOLLERANZA = 300;

	public static function content_digest( string $corpo ): string {
		return 'sha-256=:' . base64_encode( hash( 'sha256', $corpo, true ) ) . ':';
	}

	/** Elemento di un campo strutturato (RFC 8941): stringa, intero o sequenza di byte. */
	public static function elemento( $valore ): string {
		if ( is_int( $valore ) ) {
			return (string) $valore;
		}
		if ( is_array( $valore ) && isset( $valore['byte'] ) ) {
			return ':' . base64_encode( $valore['byte'] ) . ':';
		}
		return '"' . str_replace( array( '\\', '"' ), array( '\\\\', '\\"' ), (string) $valore ) . '"';
	}

	/**
	 * Lista interna dei componenti con i parametri, es.
	 * ("@method" "@path");created=1;keyid="x". $componenti: [[nome, [[param, valore], ...]], ...].
	 */
	public static function lista_interna( array $componenti, array $parametri ): string {
		$voci = array();
		foreach ( $componenti as $c ) {
			$voci[] = self::elemento( $c[0] ) . self::parametri( $c[1] ?? array() );
		}
		return '(' . implode( ' ', $voci ) . ')' . self::parametri( $parametri );
	}

	public static function parametri( array $parametri ): string {
		$testo = '';
		foreach ( $parametri as $p ) {
			$testo .= ';' . $p[0] . ( true === $p[1] ? '' : '=' . self::elemento( $p[1] ) );
		}
		return $testo;
	}

	/**
	 * Base della firma (RFC 9421 §2.5). $valori: [identificatore => valore] nell'ordine dei
	 * componenti, già calcolati da chi chiama.
	 */
	public static function base( array $componenti, array $valori, array $parametri ): string {
		$righe = array();
		foreach ( $componenti as $i => $c ) {
			$righe[] = self::elemento( $c[0] ) . self::parametri( $c[1] ?? array() ) . ': ' . $valori[ $i ];
		}
		$righe[] = '"@signature-params": ' . self::lista_interna( $componenti, $parametri );
		return implode( "\n", $righe );
	}

	/**
	 * Intestazioni di firma di una richiesta del contratto. $query senza "?".
	 * Restituisce le intestazioni da aggiungere (Destinatario-Istanza, Content-Digest, firme).
	 */
	public static function firma_richiesta( string $metodo, string $percorso, string $query, string $destinatario,
		?string $corpo, string $keyid, string $seme, ?int $adesso = null, ?string $nonce = null ): array {
		$adesso     = $adesso ?? time();
		$nonce      = $nonce ?? GA_Cripto::b64url( random_bytes( 24 ) );
		$intest     = array( 'Destinatario-Istanza' => $destinatario );
		$componenti = array( array( '@method' ), array( '@path' ), array( '@query' ), array( 'destinatario-istanza' ) );
		$valori     = array( strtoupper( $metodo ), $percorso === '' ? '/' : $percorso, '?' . $query, $destinatario );
		if ( null !== $corpo ) {
			$intest['Content-Digest'] = self::content_digest( $corpo );
			$componenti[]             = array( 'content-digest' );
			$valori[]                 = $intest['Content-Digest'];
		}
		$parametri = array(
			array( 'created', $adesso ),
			array( 'expires', $adesso + self::TOLLERANZA ),
			array( 'nonce', $nonce ),
			array( 'keyid', $keyid ),
			array( 'alg', 'ed25519' ),
			array( 'tag', self::TAG ),
		);
		$firma = GA_Cripto::firma( self::base( $componenti, $valori, $parametri ), $seme );
		$intest['Signature-Input'] = self::ETICHETTA . '=' . self::lista_interna( $componenti, $parametri );
		$intest['Signature']       = self::ETICHETTA . '=' . self::elemento( array( 'byte' => $firma ) );
		return $intest;
	}

	/** Membri di un dizionario strutturato come testo grezzo: [nome => valore grezzo]. */
	public static function membri( string $campo ): array {
		$membri = array();
		$n      = strlen( $campo );
		$i      = 0;
		while ( $i < $n ) {
			while ( $i < $n && ( $campo[ $i ] === ' ' || $campo[ $i ] === "\t" || $campo[ $i ] === ',' ) ) {
				$i++;
			}
			if ( ! preg_match( '/\G([a-z*][a-z0-9_\-.*]*)=/', $campo, $m, 0, $i ) ) {
				break;
			}
			$nome = $m[1];
			$i   += strlen( $m[0] );
			$inizio = $i;
			$profondita = 0;
			$virgolette = false;
			for ( ; $i < $n; $i++ ) {
				$c = $campo[ $i ];
				if ( $virgolette ) {
					if ( $c === '\\' ) {
						$i++;
					} elseif ( $c === '"' ) {
						$virgolette = false;
					}
				} elseif ( $c === '"' ) {
					$virgolette = true;
				} elseif ( $c === '(' ) {
					$profondita++;
				} elseif ( $c === ')' ) {
					$profondita--;
				} elseif ( $c === ',' && 0 === $profondita ) {
					break;
				}
			}
			$membri[ $nome ] = trim( substr( $campo, $inizio, $i - $inizio ) );
		}
		return $membri;
	}

	/** Componenti (con i parametri come testo) e parametri di una lista interna grezza. */
	public static function leggi_lista( string $grezza ): array {
		if ( ! preg_match( '/^\((.*)\)(.*)$/s', $grezza, $m ) ) {
			throw new GA_Errore_Firma( 'Signature-Input non valido' );
		}
		preg_match_all( '/"([^"]*)"((?:;[a-z0-9_\-.*]+(?:=(?:"[^"]*"|[^;\s)]+))?)*)/', $m[1], $voci, PREG_SET_ORDER );
		preg_match_all( '/;([a-z0-9_\-.*]+)=("([^"]*)"|-?\d+)/', $m[2], $par, PREG_SET_ORDER );
		$parametri = array();
		foreach ( $par as $p ) {
			$parametri[ $p[1] ] = isset( $p[3] ) && $p[3] !== '' ? $p[3] : ( is_numeric( $p[2] ) ? (int) $p[2] : trim( $p[2], '"' ) );
		}
		return array(
			array_map( fn( $v ) => array( $v[1], $v[2] ), $voci ),
			$parametri,
		);
	}

	/**
	 * Verifica la firma «ga» di una risposta del gestionale: contenuto integro, legata alla
	 * nostra richiesta, chiave dell'istanza. $chiavi: JWKS dell'istanza.
	 */
	public static function verifica_risposta( int $stato, array $intestazioni, string $corpo, string $firma_richiesta, array $chiavi, ?int $adesso = null ): void {
		$intestazioni = array_change_key_case( $intestazioni, CASE_LOWER );
		$digest       = $intestazioni['content-digest'] ?? '';
		if ( $digest !== self::content_digest( $corpo ) ) {
			throw new GA_Errore_Firma( 'Content-Digest della risposta non valido' );
		}
		$ingressi = self::membri( $intestazioni['signature-input'] ?? '' );
		$valori   = self::membri( $intestazioni['signature'] ?? '' );
		$errore   = 'risposta senza firma valida';
		foreach ( $ingressi as $etichetta => $grezza ) {
			if ( ! preg_match( '/^ga\d*$/', $etichetta ) || ! isset( $valori[ $etichetta ] ) ) {
				continue;
			}
			list( $componenti, $parametri ) = self::leggi_lista( $grezza );
			$nomi = array_map( fn( $c ) => $c[0] . $c[1], $componenti );
			if ( array( '@status', 'content-digest', 'signature;req;key="ga"' ) !== $nomi ) {
				$errore = 'componenti della firma della risposta inattesi';
				continue;
			}
			$chiave = null;
			foreach ( $chiavi['keys'] ?? array() as $k ) {
				if ( ( $k['kid'] ?? '' ) === ( $parametri['keyid'] ?? null ) && ( $k['use'] ?? '' ) === 'sig' ) {
					$chiave = $k;
				}
			}
			if ( null === $chiave ) {
				$errore = 'chiave della risposta sconosciuta (rileggere la JWKS)';
				continue;
			}
			$righe = array(
				'"@status": ' . $stato,
				'"content-digest": ' . $digest,
				'"signature";req;key="ga": ' . $firma_richiesta,
				'"@signature-params": ' . $grezza,
			);
			if ( ! preg_match( '/^:([A-Za-z0-9+\/=]*):$/', $valori[ $etichetta ], $b ) ) {
				continue;
			}
			if ( GA_Cripto::verifica( base64_decode( $b[1] ), implode( "\n", $righe ), $chiave['x'] ) ) {
				$adesso = $adesso ?? time();
				if ( isset( $parametri['created'] ) && abs( $adesso - (int) $parametri['created'] ) > self::TOLLERANZA ) {
					throw new GA_Errore_Firma( 'orologio della risposta fuori tolleranza' );
				}
				return;
			}
			$errore = 'firma della risposta non valida';
		}
		throw new GA_Errore_Firma( $errore );
	}
}
