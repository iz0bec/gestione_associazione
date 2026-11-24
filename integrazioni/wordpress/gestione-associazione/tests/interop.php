<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Prova incrociata con il gestionale (usata dai test Python): riceve un comando in
 *              JSON su stdin e risponde in JSON (chiavi, cifratura, decifratura, firma di una
 *              richiesta, verifica di una risposta). Solo per i test, mai sul sito.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( PHP_SAPI !== 'cli' ) {
	exit;
}
require __DIR__ . '/../includes/cripto.php';
require __DIR__ . '/../includes/firma.php';

$in = json_decode( stream_get_contents( STDIN ), true );
try {
	switch ( $in['comando'] ) {
		case 'chiavi':
			$chiavi = GA_Cripto::genera_chiavi();
			$out    = array( 'chiavi' => $chiavi, 'jwks' => GA_Cripto::jwks( $chiavi ) );
			break;
		case 'cifra':
			$out = array( 'jwe' => GA_Cripto::cifra( $in['testo'], $in['jwk'] ) );
			break;
		case 'decifra':
			$out = array( 'testo' => GA_Cripto::decifra( $in['jwe'], $in['segreto'] ) );
			break;
		case 'firma_richiesta':
			$out = array( 'intestazioni' => GA_Firma::firma_richiesta( $in['metodo'], $in['percorso'], $in['query'],
				$in['destinatario'], $in['corpo'], $in['keyid'], $in['seme'] ) );
			break;
		case 'verifica_risposta':
			GA_Firma::verifica_risposta( $in['stato'], $in['intestazioni'], $in['corpo'], $in['firma_richiesta'], $in['jwks'] );
			$out = array( 'valida' => true );
			break;
		case 'impronta':
			$out = array( 'impronta' => GA_Cripto::impronta_abbinamento( $in['a'], $in['b'] ) );
			break;
		default:
			$out = array( 'errore' => 'comando sconosciuto' );
	}
} catch ( Throwable $e ) {
	$out = array( 'errore' => $e->getMessage() );
}
echo json_encode( $out );
