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

  // Finestre modali: aperte al caricamento (data-modale-aperto) o all'invio di un modulo
  // (data-modale-invio="#id"), es. avanzamento delle importazioni
  function apriModale(el) {
    var bs = window.tabler && window.tabler.bootstrap;
    if (bs && bs.Modal) bs.Modal.getOrCreateInstance(el).show();
  }
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-modale-aperto]").forEach(apriModale);
  });
  document.addEventListener("submit", function (ev) {
    var modulo = ev.target.closest("form[data-modale-invio]");
    if (!modulo || ev.defaultPrevented) return;
    var modale = document.querySelector(modulo.getAttribute("data-modale-invio"));
    if (modale) apriModale(modale);
  });

  // Select che inviano il modulo al cambio (es. scelta dell'anno)
  document.addEventListener("change", function (ev) {
    if (ev.target.matches("select[data-invio-automatico]") && ev.target.form) {
      ev.target.form.requestSubmit();
    }
  });

  // Ricerche dentro un modulo (es. scelta dei corrispondenti): Invio non invia il modulo
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && ev.target.matches("input[data-ricerca-scelta]")) ev.preventDefault();
  });

  // Modulo protocollo: sezioni visibili secondo la direzione (data-direzioni="entrata interno")
  function aggiornaDirezione(modulo) {
    var scelta = modulo.querySelector("input[name=direzione]:checked");
    var direzione = scelta ? scelta.value : "entrata";
    modulo.querySelectorAll("[data-direzioni]").forEach(function (el) {
      var ammesse = el.getAttribute("data-direzioni").split(" ");
      el.classList.toggle("nascosto", ammesse.indexOf(direzione) === -1);
    });
  }

  // Sezioni visibili secondo una scelta: <form o div data-mostra-secondo="tipo"> e <div data-valori="a b">
  function aggiornaSecondo(modulo) {
    var nome = modulo.getAttribute("data-mostra-secondo");
    var scelta = modulo.querySelector("input[name='" + nome + "']:checked");
    var valore = scelta ? scelta.value : "";
    modulo.querySelectorAll("[data-valori]").forEach(function (el) {
      el.classList.toggle("nascosto", el.getAttribute("data-valori").split(" ").indexOf(valore) === -1);
    });
  }

  // Modulo anagrafica: mostra i campi di persona o di ente secondo il tipo scelto
  function aggiornaTipoSoggetto(modulo) {
    var scelto = modulo.querySelector("input[name=tipo]:checked");
    var tipo = scelto ? scelto.value : "persona";
    modulo.querySelectorAll(".solo-persona").forEach(function (el) { el.classList.toggle("nascosto", tipo !== "persona"); });
    modulo.querySelectorAll(".solo-ente").forEach(function (el) { el.classList.toggle("nascosto", tipo !== "ente"); });
  }
  function inizializza(radice) {
    radice.querySelectorAll("[data-mostra-secondo]").forEach(function (modulo) {
      aggiornaSecondo(modulo);
      modulo.addEventListener("change", function (ev) {
        if (ev.target.name === modulo.getAttribute("data-mostra-secondo")) aggiornaSecondo(modulo);
      });
    });
    radice.querySelectorAll("form[data-modulo-protocollo]").forEach(function (modulo) {
      aggiornaDirezione(modulo);
      modulo.addEventListener("change", function (ev) {
        if (ev.target.name === "direzione") aggiornaDirezione(modulo);
      });
    });
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
