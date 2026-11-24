<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Test da riga di comando della crittografia e della firma (senza WordPress):
 *              vettori ufficiali RFC 9421 (B.2.6) e RFC 3394, JWE di andata e ritorno, impronte,
 *              firma e verifica di richieste e risposte. Uso: php tests/esegui.php
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

require __DIR__ . '/../includes/cripto.php';
require __DIR__ . '/../includes/firma.php';

$falliti = 0;
$fatti   = 0;

function controlla( string $nome, bool $esito ): void {
	global $falliti, $fatti;
	$fatti++;
	if ( ! $esito ) {
		$falliti++;
		fwrite( STDERR, "FALLITO: $nome\n" );
	}
}

// RFC 9421, Appendice B.1.4 (test-key-ed25519): seme = ultimi 32 byte della chiave PKCS#8
$pkcs8 = base64_decode( 'MC4CAQAwBQYDK2VwBCIEIJ+DYvh6SEqVTm50DFtMDoQikTmiCqirVv9mWG9qfSnF' );
$seme  = GA_Cripto::b64url( substr( $pkcs8, -32 ) );
$componenti = array( array( 'date' ), array( '@method' ), array( '@path' ), array( '@authority' ), array( 'content-type' ), array( 'content-length' ) );
$valori     = array( 'Tue, 20 Apr 2021 02:07:55 GMT', 'POST', '/foo', 'example.com', 'application/json', '18' );
$parametri  = array( array( 'created', 1618884473 ), array( 'keyid', 'test-key-ed25519' ) );
$base       = GA_Firma::base( $componenti, $valori, $parametri );
controlla( 'base RFC 9421 B.2.6', $base === "\"date\": Tue, 20 Apr 2021 02:07:55 GMT\n\"@method\": POST\n\"@path\": /foo\n\"@authority\": example.com\n\"content-type\": application/json\n\"content-length\": 18\n\"@signature-params\": (\"date\" \"@method\" \"@path\" \"@authority\" \"content-type\" \"content-length\");created=1618884473;keyid=\"test-key-ed25519\"" );
controlla( 'firma RFC 9421 B.2.6', base64_encode( GA_Cripto::firma( $base, $seme ) ) === 'wqcAqbmYJ2ji2glfAMaRy4gruYYnx2nEFN2HN6jrnDnQCK1u02Gb04v9EDgwUPiu4A0w6vuQv5lIp5WPpBKRCw==' );

// RFC 9530: Content-Digest di {"hello": "world"} + "\n"
controlla( 'content-digest RFC 9530', GA_Firma::content_digest( "{\"hello\": \"world\"}\n" ) === 'sha-256=:RK/0qy18MlBSVnWgjwz6lZEWjP/lF5HF9bvEF8FabDg=:' );

// RFC 3394 §4.6: chiave di 256 bit avvolta con KEK di 256 bit
$kek     = hex2bin( '000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F' );
$chiave  = hex2bin( '00112233445566778899AABBCCDDEEFF000102030405060708090A0B0C0D0E0F' );
$attesa  = '28C9F404C4B810F4CBCCB35CFB87F8263F5786E2D80ED326CBC7F0E71A99F43BFB988B9B7A02DD21';
controlla( 'AES Key Wrap RFC 3394', strtoupper( bin2hex( GA_Cripto::avvolgi( $kek, $chiave ) ) ) === $attesa );
controlla( 'AES Key Unwrap RFC 3394', GA_Cripto::svolgi( $kek, hex2bin( $attesa ) ) === $chiave );

// RFC 7638 §3.1 non è OKP: impronta della chiave Ed25519 di RFC 8037 §A.3
controlla( 'impronta RFC 8037 A.3', GA_Cripto::impronta_jwk( array( 'crv' => 'Ed25519', 'kty' => 'OKP', 'x' => '11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo' ) ) === 'kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k' );

// chiavi del sito, JWE di andata e ritorno
$sito  = GA_Cripto::genera_chiavi();
$jwks  = GA_Cripto::jwks( $sito );
controlla( 'JWKS con firma e cifratura', count( $jwks['keys'] ) === 2 && $jwks['keys'][1]['crv'] === 'X25519' );
$jwe   = GA_Cripto::cifra( '{"nome":"Mario"}', $jwks['keys'][1] );
controlla( 'JWE andata e ritorno', GA_Cripto::decifra( $jwe, $sito['cifratura'] ) === '{"nome":"Mario"}' );
$alterato = explode( '.', $jwe );
$alterato[3] = GA_Cripto::b64url( 'xxxxxxxxxxxxxxxx' );
try {
	GA_Cripto::decifra( implode( '.', $alterato ), $sito['cifratura'] );
	controlla( 'JWE alterato rifiutato', false );
} catch ( GA_Errore_Cripto $e ) {
	controlla( 'JWE alterato rifiutato', true );
}
controlla( 'sigillo delle chiavi', GA_Cripto::apri( GA_Cripto::sigilla( 'segreto', 'materiale' ), 'materiale' ) === 'segreto' );

// richiesta firmata e risposta firmata dall'«istanza» (simulata con un'altra coppia di chiavi)
$istanza = GA_Cripto::genera_chiavi();
$jwks_i  = GA_Cripto::jwks( $istanza );
$intest  = GA_Firma::firma_richiesta( 'POST', '/api/v1/contatti', '', 'uuid-istanza', '{}', $jwks['keys'][0]['kid'], $sito['firma'], 1000, str_repeat( 'n', 20 ) );
controlla( 'Signature-Input della richiesta', str_starts_with( $intest['Signature-Input'], 'ga=("@method" "@path" "@query" "destinatario-istanza" "content-digest");created=1000;expires=1300;nonce="nnnnnnnnnnnnnnnnnnnn";keyid=' ) );
$membro_richiesta = GA_Firma::membri( $intest['Signature'] )['ga'];
$corpo_risposta   = '{"ricevuto":true}';
$digest           = GA_Firma::content_digest( $corpo_risposta );
$lista            = '("@status" "content-digest" "signature";req;key="ga");created=1001;expires=1301;nonce="mmmmmmmmmmmmmmmmmmmm";keyid="' . $jwks_i['keys'][0]['kid'] . '";alg="ed25519";tag="ga-v1"';
$base_risposta    = "\"@status\": 201\n\"content-digest\": $digest\n\"signature\";req;key=\"ga\": $membro_richiesta\n\"@signature-params\": $lista";
$firma_risposta   = GA_Cripto::firma( $base_risposta, $istanza['firma'] );
$intest_risposta  = array( 'Content-Digest' => $digest, 'Signature-Input' => "ga=$lista", 'Signature' => 'ga=:' . base64_encode( $firma_risposta ) . ':' );
try {
	GA_Firma::verifica_risposta( 201, $intest_risposta, $corpo_risposta, $membro_richiesta, $jwks_i, 1001 );
	controlla( 'risposta firmata verificata', true );
} catch ( GA_Errore_Firma $e ) {
	controlla( 'risposta firmata verificata: ' . $e->getMessage(), false );
}
try {
	GA_Firma::verifica_risposta( 200, $intest_risposta, $corpo_risposta, $membro_richiesta, $jwks_i, 1001 );
	controlla( 'risposta con stato alterato rifiutata', false );
} catch ( GA_Errore_Firma $e ) {
	controlla( 'risposta con stato alterato rifiutata', true );
}
controlla( 'impronta di abbinamento simmetrica', GA_Cripto::impronta_abbinamento( $jwks, $jwks_i ) === GA_Cripto::impronta_abbinamento( $jwks_i, $jwks ) );

printf( "%d controlli, %d falliti\n", $fatti, $falliti );
exit( $falliti ? 1 : 0 );
