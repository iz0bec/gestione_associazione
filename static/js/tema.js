/* ******************************************************
 * Progetto:    Gestione Associazione
 * Autore:      Bartolomeo Santoro aka IZ0BEC
 * Email:       info@iz0bec.info
 * Descrizione: Applica il tema chiaro/scuro e il menu laterale nascosto prima del disegno della pagina
 * Licenza:     CC0 1.0 Universal (pubblico dominio)
 * SPDX-License-Identifier: CC0-1.0
 * ****************************************************** */
(function () {
  var tema = null;
  try { tema = localStorage.getItem("tema"); } catch (e) { /* storage non disponibile */ }
  if (tema !== "light" && tema !== "dark") {
    tema = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-bs-theme", tema);
  var menu = null;
  try { menu = localStorage.getItem("menu"); } catch (e) { /* storage non disponibile */ }
  if (menu === "nascosto") document.documentElement.classList.add("menu-nascosto");
})();
