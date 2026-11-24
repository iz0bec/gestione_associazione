<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Crittografia del contratto API v1 senza librerie esterne (solo sodium e openssl):
 *              base64url, impronte JWK (RFC 7638), Ed25519, X25519, Concat KDF, AES Key Wrap
 *              (RFC 3394), JWE compatto ECDH-ES+A256KW / A256GCM (RFC 7516/7518/8037).
 *              Nessuna funzione di WordPress: si prova anche da riga di comando.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) && PHP_SAPI !== 'cli' ) {
	exit;
}

class GA_Errore_Cripto extends RuntimeException {}

final class GA_Cripto {

	const ALG = 'ECDH-ES+A256KW';
	const ENC = 'A256GCM';

	public static function b64url( string $dati ): string {
		return rtrim( strtr( base64_encode( $dati ), '+/', '-_' ), '=' );
	}

	public static function b64url_decodifica( string $testo ): string {
		if ( ! preg_match( '/^[A-Za-z0-9_-]*$/', $testo ) ) {
			throw new GA_Errore_Cripto( 'base64url non valido' );
		}
		$dati = base64_decode( strtr( $testo, '-_', '+/' ) . str_repeat( '=', ( 4 - strlen( $testo ) % 4 ) % 4 ), true );
		if ( false === $dati ) {
			throw new GA_Errore_Cripto( 'base64url non valido' );
		}
		return $dati;
	}

	/** Impronta RFC 7638 di una chiave OKP (membri obbligatori in ordine, senza spazi). */
	public static function impronta_jwk( array $jwk ): string {
		$canonico = '{"crv":"' . $jwk['crv'] . '","kty":"' . $jwk['kty'] . '","x":"' . $jwk['x'] . '"}';
		return self::b64url( hash( 'sha256', $canonico, true ) );
	}

	// --- chiavi -------------------------------------------------------------------------------

	/** Nuove chiavi del sito: seme Ed25519 (firma) e segreto X25519 (cifratura). */
	public static function genera_chiavi(): array {
		return array(
			'firma'      => self::b64url( random_bytes( SODIUM_CRYPTO_SIGN_SEEDBYTES ) ),
			'cifratura'  => self::b64url( random_bytes( SODIUM_CRYPTO_SCALARMULT_SCALARBYTES ) ),
		);
	}

	public static function segreta_firma( string $seme_b64 ): string {
		$coppia = sodium_crypto_sign_seed_keypair( self::b64url_decodifica( $seme_b64 ) );
		return sodium_crypto_sign_secretkey( $coppia );
	}

	public static function pubblica_firma( string $seme_b64 ): string {
		$coppia = sodium_crypto_sign_seed_keypair( self::b64url_decodifica( $seme_b64 ) );
		return sodium_crypto_sign_publickey( $coppia );
	}

	public static function pubblica_cifratura( string $segreto_b64 ): string {
		return sodium_crypto_scalarmult_base( self::b64url_decodifica( $segreto_b64 ) );
	}

	/** JWKS pubblico del sito, da presentare all'abbinamento. */
	public static function jwks( array $chiavi ): array {
		$firma     = array( 'kty' => 'OKP', 'crv' => 'Ed25519', 'x' => self::b64url( self::pubblica_firma( $chiavi['firma'] ) ), 'use' => 'sig' );
		$cifratura = array( 'kty' => 'OKP', 'crv' => 'X25519', 'x' => self::b64url( self::pubblica_cifratura( $chiavi['cifratura'] ) ), 'use' => 'enc' );
		$firma['kid']     = self::impronta_jwk( $firma );
		$cifratura['kid'] = self::impronta_jwk( $cifratura );
		return array( 'keys' => array( $firma, $cifratura ) );
	}

	public static function firma( string $messaggio, string $seme_b64 ): string {
		return sodium_crypto_sign_detached( $messaggio, self::segreta_firma( $seme_b64 ) );
	}

	public static function verifica( string $firma, string $messaggio, string $pubblica_b64 ): bool {
		$pubblica = self::b64url_decodifica( $pubblica_b64 );
		if ( strlen( $pubblica ) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES || strlen( $firma ) !== SODIUM_CRYPTO_SIGN_BYTES ) {
			return false;
		}
		return sodium_crypto_sign_verify_detached( $firma, $messaggio, $pubblica );
	}

	/**
	 * Impronta comune dell'abbinamento: SHA-256 delle impronte delle chiavi in uso di entrambe le
	 * parti, ordinate e unite da "\n"; 32 cifre esadecimali maiuscole in gruppi di 4.
	 */
	public static function impronta_abbinamento( array $jwks_a, array $jwks_b ): string {
		$impronte = array();
		foreach ( array( $jwks_a, $jwks_b ) as $jwks ) {
			foreach ( $jwks['keys'] ?? array() as $k ) {
				if ( ! isset( $k['exp'] ) ) {
					$impronte[] = self::impronta_jwk( $k );
				}
			}
		}
		sort( $impronte, SORT_STRING );
		$esa = strtoupper( substr( hash( 'sha256', implode( "\n", $impronte ) ), 0, 32 ) );
		return implode( ' ', str_split( $esa, 4 ) );
	}

	// --- JWE ----------------------------------------------------------------------------------

	private static function lunghezza( string $dati ): string {
		return pack( 'N', strlen( $dati ) ) . $dati;
	}

	/** Concat KDF (NIST SP 800-56A) come in RFC 7518 §4.6.2, con SHA-256. */
	public static function concat_kdf( string $z, string $algoritmo, int $bit, string $apu = '', string $apv = '' ): string {
		$altre  = self::lunghezza( $algoritmo ) . self::lunghezza( $apu ) . self::lunghezza( $apv ) . pack( 'N', $bit );
		$uscita = '';
		for ( $giro = 1; strlen( $uscita ) * 8 < $bit; $giro++ ) {
			$uscita .= hash( 'sha256', pack( 'N', $giro ) . $z . $altre, true );
		}
		return substr( $uscita, 0, intdiv( $bit, 8 ) );
	}

	private static function aes_blocco( string $chiave, string $blocco, bool $cifra ): string {
		$fn       = $cifra ? 'openssl_encrypt' : 'openssl_decrypt';
		$risultato = $fn( $blocco, 'aes-256-ecb', $chiave, OPENSSL_RAW_DATA | OPENSSL_ZERO_PADDING );
		if ( false === $risultato ) {
			throw new GA_Errore_Cripto( 'AES non disponibile' );
		}
		return $risultato;
	}

	/** AES Key Wrap (RFC 3394) con IV predefinito A6A6A6A6A6A6A6A6. */
	public static function avvolgi( string $kek, string $chiave ): string {
		$a = hex2bin( 'A6A6A6A6A6A6A6A6' );
		$r = str_split( $chiave, 8 );
		$n = count( $r );
		for ( $j = 0; $j <= 5; $j++ ) {
			for ( $i = 1; $i <= $n; $i++ ) {
				$b       = self::aes_blocco( $kek, $a . $r[ $i - 1 ], true );
				$t       = $n * $j + $i;
				$a       = substr( $b, 0, 8 ) ^ pack( 'J', $t );
				$r[ $i - 1 ] = substr( $b, 8, 8 );
			}
		}
		return $a . implode( '', $r );
	}

	public static function svolgi( string $kek, string $avvolta ): string {
		if ( strlen( $avvolta ) % 8 !== 0 || strlen( $avvolta ) < 24 ) {
			throw new GA_Errore_Cripto( 'chiave avvolta non valida' );
		}
		$a = substr( $avvolta, 0, 8 );
		$r = str_split( substr( $avvolta, 8 ), 8 );
		$n = count( $r );
		for ( $j = 5; $j >= 0; $j-- ) {
			for ( $i = $n; $i >= 1; $i-- ) {
				$t       = $n * $j + $i;
				$b       = self::aes_blocco( $kek, ( $a ^ pack( 'J', $t ) ) . $r[ $i - 1 ], false );
				$a       = substr( $b, 0, 8 );
				$r[ $i - 1 ] = substr( $b, 8, 8 );
			}
		}
		if ( ! hash_equals( hex2bin( 'A6A6A6A6A6A6A6A6' ), $a ) ) {
			throw new GA_Errore_Cripto( 'integrità della chiave avvolta non verificata' );
		}
		return implode( '', $r );
	}

	/** JWE compatto per la chiave X25519 (use=enc) del destinatario. */
	public static function cifra( string $contenuto, array $jwk_destinatario, string $cty = 'application/json' ): string {
		if ( ( $jwk_destinatario['crv'] ?? '' ) !== 'X25519' ) {
			throw new GA_Errore_Cripto( 'serve la chiave di cifratura X25519 del destinatario' );
		}
		$effimera  = random_bytes( SODIUM_CRYPTO_SCALARMULT_SCALARBYTES );
		$z         = sodium_crypto_scalarmult( $effimera, self::b64url_decodifica( $jwk_destinatario['x'] ) );
		$kek       = self::concat_kdf( $z, self::ALG, 256 );
		$cek       = random_bytes( 32 );
		$testata   = array(
			'alg' => self::ALG,
			'enc' => self::ENC,
			'cty' => $cty,
			'kid' => $jwk_destinatario['kid'] ?? '',
			'epk' => array( 'kty' => 'OKP', 'crv' => 'X25519', 'x' => self::b64url( sodium_crypto_scalarmult_base( $effimera ) ) ),
		);
		$protetta  = self::b64url( json_encode( $testata, JSON_UNESCAPED_SLASHES ) );
		$iv        = random_bytes( 12 );
		$tag       = '';
		$cifrato   = openssl_encrypt( $contenuto, 'aes-256-gcm', $cek, OPENSSL_RAW_DATA, $iv, $tag, $protetta, 16 );
		if ( false === $cifrato ) {
			throw new GA_Errore_Cripto( 'AES-GCM non disponibile' );
		}
		return implode( '.', array( $protetta, self::b64url( self::avvolgi( $kek, $cek ) ), self::b64url( $iv ), self::b64url( $cifrato ), self::b64url( $tag ) ) );
	}

	/** Decifra un JWE compatto indirizzato alla chiave X25519 del sito. */
	public static function decifra( string $jwe, string $segreto_b64 ): string {
		$parti = explode( '.', trim( $jwe ) );
		if ( count( $parti ) !== 5 ) {
			throw new GA_Errore_Cripto( 'JWE compatto non valido' );
		}
		$testata = json_decode( self::b64url_decodifica( $parti[0] ), true );
		if ( ! is_array( $testata ) || ( $testata['alg'] ?? '' ) !== self::ALG || ( $testata['enc'] ?? '' ) !== self::ENC ) {
			throw new GA_Errore_Cripto( 'algoritmi del JWE non supportati' );
		}
		$z   = sodium_crypto_scalarmult( self::b64url_decodifica( $segreto_b64 ), self::b64url_decodifica( $testata['epk']['x'] ?? '' ) );
		$kek = self::concat_kdf( $z, self::ALG, 256 );
		$cek = self::svolgi( $kek, self::b64url_decodifica( $parti[1] ) );
		$chiaro = openssl_decrypt( self::b64url_decodifica( $parti[3] ), 'aes-256-gcm', $cek, OPENSSL_RAW_DATA,
			self::b64url_decodifica( $parti[2] ), self::b64url_decodifica( $parti[4] ), $parti[0] );
		if ( false === $chiaro ) {
			throw new GA_Errore_Cripto( 'decifratura non riuscita' );
		}
		return $chiaro;
	}

	// --- conservazione delle chiavi nel database di WordPress ----------------------------------

	/** Cifra le chiavi del sito con una chiave derivata dalle chiavi segrete di wp-config.php. */
	public static function sigilla( string $testo, string $materiale ): string {
		$chiave = sodium_crypto_generichash( 'gestione-associazione|' . $materiale, '', SODIUM_CRYPTO_SECRETBOX_KEYBYTES );
		$nonce  = random_bytes( SODIUM_CRYPTO_SECRETBOX_NONCEBYTES );
		return self::b64url( $nonce . sodium_crypto_secretbox( $testo, $nonce, $chiave ) );
	}

	public static function apri( string $sigillato, string $materiale ): string {
		$chiave = sodium_crypto_generichash( 'gestione-associazione|' . $materiale, '', SODIUM_CRYPTO_SECRETBOX_KEYBYTES );
		$dati   = self::b64url_decodifica( $sigillato );
		$testo  = sodium_crypto_secretbox_open( substr( $dati, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES ),
			substr( $dati, 0, SODIUM_CRYPTO_SECRETBOX_NONCEBYTES ), $chiave );
		if ( false === $testo ) {
			throw new GA_Errore_Cripto( 'chiavi del sito non leggibili: sono cambiate le chiavi segrete di wp-config.php?' );
		}
		return $testo;
	}
}
