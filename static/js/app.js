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

  // Stampe (collegamenti con data-stampa): invece di una scheda vuota durante la preparazione,
  // una finestra di attesa; a PDF pronto si apre (o si offrono «Apri» e «Scarica»).
  var stampaInCorso = null;
  function faseStampa(modale, fase) {
    modale.querySelectorAll("[data-stampa-fase]").forEach(function (el) {
      el.classList.toggle("nascosto", el.getAttribute("data-stampa-fase") !== fase);
    });
  }
  function nomeFile(intestazione) {
    var m = /filename="?([^";]+)"?/.exec(intestazione || "");
    return m ? m[1] : "documento.pdf";
  }
  function stampa(url) {
    var modale = document.getElementById("modale-stampa");
    var bs = window.tabler && window.tabler.bootstrap;
    if (!modale || !bs || !window.fetch) { window.open(url, "_blank", "noopener"); return; }
    var finestra = bs.Modal.getOrCreateInstance(modale);
    var controllo = new AbortController();
    var inizio = Date.now();
    var secondi = modale.querySelector("[data-stampa-secondi]");
    secondi.textContent = "0";
    faseStampa(modale, "attesa");
    finestra.show();
    var timer = window.setInterval(function () {
      secondi.textContent = String(Math.round((Date.now() - inizio) / 1000));
    }, 1000);
    stampaInCorso = { controllo: controllo, timer: timer };
    fetch(url, { credentials: "same-origin", signal: controllo.signal })
      .then(function (r) {
        if (!r.ok) throw new Error("Il server ha risposto con un errore (" + r.status + ").");
        if ((r.headers.get("Content-Type") || "").indexOf("application/pdf") === -1) {
          throw new Error("Risposta inattesa: forse la sessione è scaduta. Ricaricare la pagina e riprovare.");
        }
        var nome = nomeFile(r.headers.get("Content-Disposition"));
        return r.blob().then(function (b) { return { blob: b, nome: nome }; });
      })
      .then(function (doc) {
        window.clearInterval(timer);
        var indirizzo = URL.createObjectURL(doc.blob);
        window.setTimeout(function () { URL.revokeObjectURL(indirizzo); }, 30 * 60 * 1000);
        modale.querySelector("[data-stampa-apri]").href = indirizzo;
        var scarica = modale.querySelector("[data-stampa-scarica]");
        scarica.href = indirizzo;
        scarica.setAttribute("download", doc.nome);
        faseStampa(modale, "pronto");
        // apertura automatica; se il browser la blocca restano i pulsanti
        if (window.open(indirizzo, "_blank")) finestra.hide();
      })
      .catch(function (errore) {
        window.clearInterval(timer);
        if (errore.name === "AbortError") return;
        modale.querySelector("[data-stampa-errore]").textContent = errore.message;
        faseStampa(modale, "errore");
      });
  }
  document.addEventListener("click", function (ev) {
    var chiudi = ev.target.closest("[data-stampa-chiudi]");
    if (chiudi) {
      if (stampaInCorso) { stampaInCorso.controllo.abort(); window.clearInterval(stampaInCorso.timer); }
      var bs = window.tabler && window.tabler.bootstrap;
      bs.Modal.getOrCreateInstance(document.getElementById("modale-stampa")).hide();
      return;
    }
    var link = ev.target.closest("a[data-stampa]");
    if (!link || ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
    ev.preventDefault();
    stampa(link.href);
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
  // «Seleziona tutte»: <input type="checkbox" data-seleziona-tutte="nome-delle-caselle">
  document.addEventListener("change", function (ev) {
    var nome = ev.target.getAttribute && ev.target.getAttribute("data-seleziona-tutte");
    if (!nome) return;
    var modulo = ev.target.form || document;
    modulo.querySelectorAll('input[type="checkbox"][name="' + nome + '"]').forEach(function (c) {
      c.checked = ev.target.checked;
    });
  });
  document.addEventListener("DOMContentLoaded", function () { inizializza(document); });
  document.addEventListener("htmx:load", function (ev) { inizializza(ev.target); });
})();
