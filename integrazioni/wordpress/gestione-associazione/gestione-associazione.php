<?php
/**
 * Plugin Name:       Gestione Associazione
 * Plugin URI:        https://github.com/iz0bec/gestione_associazione
 * Description:       Collega il sito al gestionale Gestione Associazione (API v1, firmate e cifrate): domanda di iscrizione, modulo contatti, eventi con adesione e articoli, organigramma, verifica della tessera. Nessun dato personale dei soci sul sito.
 * Version:           0.1.1
 * Requires at least: 6.4
 * Requires PHP:      8.1
 * Author:            Bartolomeo Santoro aka IZ0BEC
 * Author URI:        https://www.iz0bec.info
 * License:           CC0-1.0
 * License URI:       https://creativecommons.org/publicdomain/zero/1.0/
 * Text Domain:       gestione-associazione
 *
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: File principale del plugin: costanti, caricamento, lavori periodici, blocchi.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'GA_VERSIONE', '0.1.1' );
define( 'GA_DIR', plugin_dir_path( __FILE__ ) );
define( 'GA_URL', plugin_dir_url( __FILE__ ) );

require_once GA_DIR . 'includes/cripto.php';
require_once GA_DIR . 'includes/firma.php';
require_once GA_DIR . 'includes/connettore.php';
require_once GA_DIR . 'includes/eventi.php';
require_once GA_DIR . 'includes/moduli.php';
require_once GA_DIR . 'includes/amministrazione.php';

// lavori periodici: ogni 15 minuti coda degli invii, eventi, organigramma, articoli
add_filter( 'cron_schedules', function ( $orari ) {
	$orari['ga_quarto_ora'] = array( 'interval' => 15 * MINUTE_IN_SECONDS, 'display' => __( 'Ogni 15 minuti', 'gestione-associazione' ) );
	return $orari;
} );
add_action( 'ga_periodico', array( 'GA_Eventi', 'periodico' ) );

register_activation_hook( __FILE__, function () {
	if ( ! extension_loaded( 'sodium' ) || ! extension_loaded( 'openssl' ) ) {
		deactivate_plugins( plugin_basename( __FILE__ ) );
		wp_die( esc_html__( 'Gestione Associazione richiede le estensioni PHP sodium e openssl.', 'gestione-associazione' ) );
	}
	if ( ! wp_next_scheduled( 'ga_periodico' ) ) {
		wp_schedule_event( time() + 60, 'ga_quarto_ora', 'ga_periodico' );
	}
} );
register_deactivation_hook( __FILE__, function () {
	wp_clear_scheduled_hook( 'ga_periodico' );
} );

GA_Moduli::avvia();
GA_Amministrazione::avvia();

// blocchi dell'editor: gli stessi moduli degli shortcode, impaginati dal server
add_action( 'init', function () {
	wp_register_script( 'gestione-associazione-blocchi', GA_URL . 'assets/blocchi.js',
		array( 'wp-blocks', 'wp-element', 'wp-components', 'wp-block-editor', 'wp-server-side-render', 'wp-i18n' ), GA_VERSIONE, true );
	$blocchi = array(
		'domanda'          => array( 'sezione' => 'string', 'statuto' => 'string', 'informativa' => 'string' ),
		'contatti'         => array(),
		'eventi'           => array( 'quanti' => 'number' ),
		'organigramma'     => array( 'sezione' => 'string' ),
		'verifica-tessera' => array(),
	);
	foreach ( $blocchi as $nome => $attributi ) {
		$shortcode = 'ga_' . str_replace( '-', '_', $nome );
		register_block_type( 'gestione-associazione/' . $nome, array(
			'editor_script'   => 'gestione-associazione-blocchi',
			'attributes'      => array_map( fn( $t ) => array( 'type' => $t ), $attributi ),
			'render_callback' => function ( $a ) use ( $shortcode ) {
				return call_user_func( array( 'GA_Moduli', 'mostra_' . substr( $shortcode, 3 ) ), array_filter( $a, fn( $v ) => '' !== $v && null !== $v ) );
			},
		) );
	}
} );
