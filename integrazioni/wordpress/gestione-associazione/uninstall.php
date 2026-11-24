<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Disinstallazione: toglie chiavi, collegamento, coda e copie in cache. Gli articoli
 *              degli eventi restano (sono contenuti del sito).
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}
foreach ( array( 'ga_connettore', 'ga_coda', 'ga_eventi', 'ga_organigramma', 'ga_articoli', 'ga_ultimo_errore' ) as $opzione ) {
	delete_option( $opzione );
}
wp_clear_scheduled_hook( 'ga_periodico' );
