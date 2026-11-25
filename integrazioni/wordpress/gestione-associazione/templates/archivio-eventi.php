<?php
/**
 * Progetto:    Gestione Associazione - connettore WordPress
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Archivio degli eventi nei temi classici: le viste del calendario (elenco, mese,
 *              giorno) dentro intestazione e piè di pagina del tema.
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

get_header();
$titolo = is_tax() ? single_term_title( '', false ) : post_type_archive_title( '', false );
?>
<main id="main" class="site-main ga-archivio-eventi">
	<div class="ga-contenitore">
		<h1 class="page-title"><?php echo esc_html( $titolo ); ?></h1>
		<?php echo GA_Calendario::vista(); // phpcs:ignore WordPress.Security.EscapeOutput -- già escapato ?>
	</div>
</main>
<?php
get_footer();
