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

  // Menu laterale nascosto o visibile (schermi larghi), ricordato nel browser
  document.addEventListener("click", function (ev) {
    var pulsante = ev.target.closest("[data-cambia-menu]");
    if (!pulsante) return;
    var nascosto = document.documentElement.classList.toggle("menu-nascosto");
    pulsante.setAttribute("aria-pressed", nascosto ? "true" : "false");
    try { localStorage.setItem("menu", nascosto ? "nascosto" : "visibile"); } catch (e) { /* ignorato */ }
  });

  // Conferma per i moduli (o i singoli pulsanti di invio) con data-conferma="testo"
  document.addEventListener("submit", function (ev) {
    var pulsante = ev.submitter && ev.submitter.closest("[data-conferma]");
    var modulo = ev.target.closest("form[data-conferma]");
    var testo = pulsante ? pulsante.getAttribute("data-conferma")
      : (modulo ? modulo.getAttribute("data-conferma") : null);
    if (testo && !window.confirm(testo)) {
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

  // Coriandoli di Tabler all'apertura (data-coriandoli + data-bs-toggle="confetti"),
  // es. il calendario con i compleanni; Tabler li salta con «riduci movimento»
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-coriandoli]").forEach(function (el) { el.click(); });
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

  // Collegamenti che seguono i filtri della pagina (data-filtri="id del modulo"; con
  // data-filtri-campi="a,b" solo quei campi): l'indirizzo si ricompone al momento dell'uso,
  // perché i filtri cambiano senza ricaricare la pagina (htmx)
  function conFiltri(link) {
    var modulo = document.getElementById(link.getAttribute("data-filtri"));
    if (!modulo) return;
    var campi = (link.getAttribute("data-filtri-campi") || "").split(",").filter(Boolean);
    var url = new URL(link.href, window.location.href);
    var fissi = new URLSearchParams(link.getAttribute("data-filtri-fissi") || "");
    var parametri = new URLSearchParams(fissi);
    new FormData(modulo).forEach(function (valore, nome) {
      if (typeof valore !== "string" || valore === "") return;
      if (campi.length && campi.indexOf(nome) === -1) return;
      parametri.append(nome, valore);
    });
    url.search = parametri.toString();
    link.href = url.toString();
  }
  ["pointerdown", "keydown", "focusin", "click"].forEach(function (tipo) {
    document.addEventListener(tipo, function (ev) {
      var link = ev.target.closest && ev.target.closest("a[data-filtri]");
      if (link) conFiltri(link);
    }, true);
  });

  // Select e interruttori che inviano il modulo al cambio (es. anno, uso di una casella)
  document.addEventListener("change", function (ev) {
    if (ev.target.matches("select[data-invio-automatico], input[data-invio-automatico]") && ev.target.form) {
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
  // Campi da copiare (es. collegamento al calendario): <input data-copia> si seleziona al clic
  document.addEventListener("click", function (ev) {
    var campo = ev.target.closest && ev.target.closest("input[data-copia]");
    if (!campo) return;
    campo.select();
    if (navigator.clipboard) navigator.clipboard.writeText(campo.value).catch(function () {});
  });
  // Codice fiscale assistito: <div data-cf-assistito="url"> sotto il campo; «Calcola» invia
  // cognome, nome, sesso, data e luogo di nascita del modulo e mostra codice, avvisi o comuni omonimi
  function campoCf(modulo, nome) { return modulo.querySelector('[name="' + nome + '"]'); }
  function valoreCf(modulo, nome) {
    var campi = modulo.querySelectorAll('[name="' + nome + '"]');
    for (var i = 0; i < campi.length; i++) {
      var c = campi[i];
      if ((c.type === "radio" || c.type === "checkbox") && !c.checked) continue;
      return c.value;
    }
    return "";
  }
  function esitoCf(box, testo, classe) {
    var esito = box.querySelector("[data-cf-esito]");
    esito.textContent = testo;
    esito.className = "small mt-1 " + (classe || "");
    return esito;
  }
  function calcolaCf(box) {
    var modulo = box.closest("form");
    var dati = new FormData();
    ["cognome", "nome", "data_nascita", "luogo_nascita", "codice_fiscale"].forEach(function (n) {
      dati.append(n, valoreCf(modulo, n));
    });
    var sesso = box.querySelector("[data-cf-sesso]");
    dati.append("sesso", sesso ? sesso.value : valoreCf(modulo, "sesso"));
    var token = campoCf(modulo, "csrfmiddlewaretoken");
    var candidati = box.querySelector("[data-cf-candidati]");
    candidati.replaceChildren();
    esitoCf(box, "Calcolo…", "text-secondary");
    fetch(box.dataset.cfAssistito, {
      method: "POST", body: dati, credentials: "same-origin",
      headers: { "X-CSRFToken": token ? token.value : "" },
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (r) {
        var campo = campoCf(modulo, "codice_fiscale");
        if (r.candidati && r.candidati.length) {
          esitoCf(box, r.errore, "text-warning");
          r.candidati.forEach(function (etichetta) {
            var b = document.createElement("button");
            b.type = "button"; b.className = "btn btn-sm btn-outline-secondary"; b.textContent = etichetta;
            b.addEventListener("click", function () {
              var luogo = campoCf(modulo, "luogo_nascita");
              if (luogo) luogo.value = etichetta;
              calcolaCf(box);
            });
            candidati.appendChild(b);
          });
        } else if (r.errore) {
          esitoCf(box, r.errore, "text-danger");
        } else if (!campo.value.trim()) {
          campo.value = r.codice;
          esitoCf(box, "Calcolato dai dati: verificarlo sulla tessera sanitaria.", "text-success");
        } else if (campo.value.trim().toUpperCase() === r.codice) {
          esitoCf(box, "Corrisponde ai dati anagrafici.", "text-success");
        } else {
          var testo = "Dai dati risulta " + r.codice + (r.avvisi.length ? " (" + r.avvisi.join(", ") + ")" : "") + ". ";
          var esito = esitoCf(box, testo, "text-warning");
          var usa = document.createElement("button");
          usa.type = "button"; usa.className = "btn btn-sm btn-link p-0 align-baseline"; usa.textContent = "Usa questo";
          usa.addEventListener("click", function () { campo.value = r.codice; esitoCf(box, "Codice sostituito: verificarlo sulla tessera sanitaria.", "text-success"); });
          esito.appendChild(usa);
        }
      })
      .catch(function () { esitoCf(box, "Calcolo non riuscito: riprovare.", "text-danger"); });
  }
  document.addEventListener("click", function (ev) {
    var pulsante = ev.target.closest("[data-cf-calcola]");
    if (pulsante) calcolaCf(pulsante.closest("[data-cf-assistito]"));
  });
  // Chat interna: l'area dei messaggi resta in fondo (se ci si era), Invio spedisce,
  // Maiusc+Invio va a capo, il modulo si svuota dopo l'invio e mostra gli errori
  function chatInFondo(area, forza) {
    if (forza || area.scrollHeight - area.scrollTop - area.clientHeight < 120) {
      area.scrollTop = area.scrollHeight;
    }
  }
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-chat-messaggi]").forEach(function (a) { chatInFondo(a, true); });
  });
  document.addEventListener("htmx:beforeSwap", function (ev) {
    var area = ev.detail.target && ev.detail.target.closest && ev.detail.target.closest("[data-chat-messaggi]");
    if (area && area.dataset.inFondo !== "1") {
      area.dataset.inFondo = area.scrollHeight - area.scrollTop - area.clientHeight < 120 ? "1" : "";
    }
  });
  document.addEventListener("htmx:afterSettle", function (ev) {
    var area = document.querySelector("[data-chat-messaggi]");
    if (!area || !ev.detail.elt) return;
    if (area.dataset.inFondo === "1") chatInFondo(area, true);
    area.dataset.inFondo = "";
    if (area.querySelector("[id^='m']")) {
      var vuota = area.querySelector("[data-chat-vuota]");
      if (vuota) vuota.remove();
    }
  });
  document.addEventListener("keydown", function (ev) {
    var campo = ev.target.closest && ev.target.closest("[data-chat-testo]");
    if (!campo || ev.key !== "Enter" || ev.shiftKey || ev.isComposing) return;
    ev.preventDefault();
    if (campo.value.trim()) campo.form.requestSubmit();
  });
  document.addEventListener("htmx:afterRequest", function (ev) {
    var modulo = ev.detail.elt && ev.detail.elt.closest && ev.detail.elt.closest("[data-chat-modulo]");
    if (!modulo) return;
    var errore = modulo.querySelector("[data-chat-errore]");
    if (ev.detail.successful) {
      modulo.reset();
      if (errore) errore.textContent = "";
      var area = document.querySelector("[data-chat-messaggi]");
      if (area) area.dataset.inFondo = "1";
      modulo.querySelector("[data-chat-testo]").focus();
    } else if (errore) {
      errore.textContent = ev.detail.xhr && ev.detail.xhr.status === 422
        ? ev.detail.xhr.responseText : "Messaggio non inviato: riprova.";
    }
  });

  document.addEventListener("DOMContentLoaded", function () { inizializza(document); });
  document.addEventListener("htmx:load", function (ev) { inizializza(ev.target); });
})();
