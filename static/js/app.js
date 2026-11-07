/* ******************************************************
 * Progetto:    Gestione Associazione
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Comportamenti dell'interfaccia (nessuno script inline: CSP rigorosa)
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 * ****************************************************** */
(function () {
  "use strict";

  // Cambio tema chiaro/scuro
  document.addEventListener("click", function (ev) {
    var pulsante = ev.target.closest("[data-cambia-tema]");
    if (!pulsante) return;
    var attuale = document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
    var nuovo = attuale === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-bs-theme", nuovo);
    try { localStorage.setItem("tema", nuovo); } catch (e) { /* ignorato */ }
  });

  // Conferma per i moduli con data-conferma="testo"
  document.addEventListener("submit", function (ev) {
    var modulo = ev.target.closest("form[data-conferma]");
    if (modulo && !window.confirm(modulo.getAttribute("data-conferma"))) {
      ev.preventDefault();
    }
  });

  // Modulo anagrafica: mostra i campi di persona o di ente secondo il tipo scelto
  function aggiornaTipoSoggetto(modulo) {
    var scelto = modulo.querySelector("input[name=tipo]:checked");
    var tipo = scelto ? scelto.value : "persona";
    modulo.querySelectorAll(".solo-persona").forEach(function (el) { el.classList.toggle("nascosto", tipo !== "persona"); });
    modulo.querySelectorAll(".solo-ente").forEach(function (el) { el.classList.toggle("nascosto", tipo !== "ente"); });
  }
  function inizializza(radice) {
    radice.querySelectorAll("form[data-modulo-soggetto]").forEach(function (modulo) {
      aggiornaTipoSoggetto(modulo);
      modulo.addEventListener("change", function (ev) {
        if (ev.target.name === "tipo") aggiornaTipoSoggetto(modulo);
      });
    });
  }
  document.addEventListener("DOMContentLoaded", function () { inizializza(document); });
  document.addEventListener("htmx:load", function (ev) { inizializza(ev.target); });
})();
