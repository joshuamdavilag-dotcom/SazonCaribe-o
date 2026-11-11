(function () {
  "use strict";

  var RUTA_PAGINAS = "paginas/";
  var EXTENSIONES = ["webp", "jpg", "jpeg", "png"];
  var MAX_PAGINAS = 40;
  var BREAKPOINT_MOVIL = 820;

  var libroEl = document.getElementById("libro");
  var overlay = document.getElementById("cargando");
  var paginaActualEl = document.getElementById("pagina-actual");
  var paginaTotalEl = document.getElementById("pagina-total");
  var barraEl = document.getElementById("barra-progreso");
  var btnPrev = document.getElementById("btn-prev");
  var btnNext = document.getElementById("btn-next");

  var pageFlip = null;
  var modoRetrato = null;
  var totalPaginas = 0;

  function existeImagen(ruta) {
    return new Promise(function (resolver) {
      var img = new Image();
      img.onload = function () { resolver(true); };
      img.onerror = function () { resolver(false); };
      img.src = ruta;
    });
  }

  async function descubrirPaginas() {
    var declaradas = parseInt(libroEl.dataset.paginas, 10);
    if (declaradas > 0 && declaradas <= MAX_PAGINAS) {
      return Array.from({ length: declaradas }, function (_, i) {
        return RUTA_PAGINAS + String(i + 1).padStart(2, "0") + ".webp";
      });
    }

    var lista = [];
    for (var i = 1; i <= MAX_PAGINAS; i++) {
      var numero = String(i).padStart(2, "0");
      var encontrada = null;
      for (var j = 0; j < EXTENSIONES.length; j++) {
        var ruta = RUTA_PAGINAS + numero + "." + EXTENSIONES[j];
        if (await existeImagen(ruta)) {
          encontrada = ruta;
          break;
        }
      }
      if (!encontrada) break;
      lista.push(encontrada);
    }
    return lista;
  }

  function crearPaginas(rutas) {
    var fragmento = document.createDocumentFragment();
    rutas.forEach(function (ruta, indice) {
      var hoja = document.createElement("div");
      hoja.className = "page" + (indice === 0 ? " page--tapa" : "");
      var img = document.createElement("img");
      img.src = ruta;
      img.alt = "Página " + (indice + 1) + " del menú";
      img.decoding = "async";
      img.draggable = false;
      hoja.appendChild(img);
      fragmento.appendChild(hoja);
    });
    libroEl.appendChild(fragmento);
  }

  function montarLibro() {
    if (pageFlip) {
      pageFlip.destroy();
      pageFlip = null;
    }

    modoRetrato = window.innerWidth < BREAKPOINT_MOVIL;

    pageFlip = new St.PageFlip(libroEl, {
      width: 600,
      height: 900,
      size: "stretch",
      minWidth: 300,
      maxWidth: 900,
      minHeight: 450,
      maxHeight: 1350,
      usePortrait: modoRetrato,
      showCover: true,
      drawShadow: true,
      flippingTime: 900,
      maxShadowOpacity: 0.45,
      showPageCorners: true,
      mobileScrollSupport: false,
      swipeDistance: 20,
      useMouseEvents: true,
      clickEventForward: true,
      disableFlipByClick: false,
      startZIndex: 0,
      autoSize: true
    });

    pageFlip.loadFromHTML(libroEl.querySelectorAll(".page"));
    pageFlip.on("flip", function (evento) {
      pintarProgreso(evento.data);
    });

    pintarProgreso(0);
    libroEl.classList.add("listo");
    if (overlay) overlay.classList.add("oculto");
  }

  function pintarProgreso(indice) {
    var actual = Math.min(totalPaginas, Math.max(1, indice + 1));
    paginaActualEl.textContent = String(actual);
    paginaTotalEl.textContent = String(totalPaginas);
    barraEl.style.width = (actual / totalPaginas) * 100 + "%";
    btnPrev.disabled = actual <= 1;
    btnNext.disabled = actual >= totalPaginas;
  }

  function siguiente() {
    if (pageFlip) pageFlip.flipNext();
  }

  function anterior() {
    if (pageFlip) pageFlip.flipPrev();
  }

  btnNext.addEventListener("click", siguiente);
  btnPrev.addEventListener("click", anterior);

  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
      e.preventDefault();
      siguiente();
    } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
      e.preventDefault();
      anterior();
    } else if (e.key === "Home") {
      pageFlip && pageFlip.turnToPage(0);
    } else if (e.key === "End") {
      pageFlip && pageFlip.turnToPage(totalPaginas - 1);
    }
  });

  var temporizadorResize = null;
  window.addEventListener("resize", function () {
    var nuevoModo = window.innerWidth < BREAKPOINT_MOVIL;
    if (nuevoModo === modoRetrato) return;
    clearTimeout(temporizadorResize);
    temporizadorResize = setTimeout(function () {
      montarLibro();
    }, 250);
  });

  async function iniciar() {
    var rutas = await descubrirPaginas();

    if (!rutas.length) {
      if (overlay) {
        overlay.innerHTML =
          '<p style="max-width:340px;text-align:center">No encontré imágenes.<br>' +
          "Coloca <b>01.webp</b>, <b>02.webp</b>, <b>03.webp</b>… dentro de la carpeta <b>paginas/</b>.</p>";
      }
      return;
    }

    totalPaginas = rutas.length;
    crearPaginas(rutas);

    var primeras = libroEl.querySelectorAll("img");
    await Promise.all(
      Array.prototype.slice.call(primeras, 0, 3).map(function (img) {
        if (img.complete) return Promise.resolve();
        return new Promise(function (r) {
          img.onload = r;
          img.onerror = r;
        });
      })
    );

    montarLibro();
  }

  iniciar();
})();
