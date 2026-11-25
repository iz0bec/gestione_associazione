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
foreach ( array( 'ga_connettore', 'ga_coda', 'ga_eventi', 'ga_organigramma', 'ga_articoli', 'ga_articoli_creati', 'ga_ultimo_errore', 'ga_eventi_creati', 'ga_calendario_flush' ) as $opzione ) {
	delete_option( $opzione );
}
// voci della coda (una per invio) e blocchi fra processi
global $wpdb;
foreach ( array( 'ga_coda_', 'ga_blocco_' ) as $prefisso ) {
	$wpdb->query( $wpdb->prepare( "DELETE FROM {$wpdb->options} WHERE option_name LIKE %s", $wpdb->esc_like( $prefisso ) . '%' ) );
}
wp_cache_flush();
wp_clear_scheduled_hook( 'ga_periodico' );
