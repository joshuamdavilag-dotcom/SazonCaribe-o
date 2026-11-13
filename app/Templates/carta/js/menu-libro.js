(function () {
  "use strict";

  var RUTA_PAGINAS_ES = "paginas/";
  var RUTA_PAGINAS_EN = "paginas/en/";
  var RUTA_PAGINAS = RUTA_PAGINAS_ES;
  var EXTENSIONES = ["webp", "jpg", "jpeg", "png"];
  var MAX_PAGINAS = 40;
  var BREAKPOINT_MOVIL = 820;
  var CLAVE_IDIOMA = "carta_idioma";

  var TEXTOS = {
    es: {
      titulo: "Sazón Caribeño — Menú",
      lema: "Cocina del Caribe",
      ampliar: "Ampliar",
      ampliarAria: "Ampliar la página para leer mejor",
      ampliarTitle: "Ampliar la página",
      preparando: "Preparando el menú…",
      libroAria: "Menú digital, libro de páginas",
      pista: "Arrastra la esquina de la hoja · usa ← → · toca <b>Ampliar</b> para leer de cerca",
      visorAria: "Página ampliada del menú",
      cerrarAria: "Cerrar y volver al libro",
      cerrarTitle: "Cerrar (Esc)",
      anteriorAria: "Página anterior",
      anteriorTitle: "Página anterior (←)",
      siguienteAria: "Página siguiente",
      siguienteTitle: "Página siguiente (→)",
      alejarAria: "Alejar",
      acercarAria: "Acercar",
      normalAria: "Tamaño normal",
      pistaVisor: "Pellizca o toca dos veces para acercar · arrastra para mover",
      pagina: "Página",
      de: "de",
      altPagina: function (n) { return "Página " + n + " del menú"; },
      altPaginaAmpliada: function (n) { return "Página " + n + " del menú, ampliada"; }
    },
    en: {
      titulo: "Sazón Caribeño — Menu",
      lema: "Caribbean Cuisine",
      ampliar: "Zoom in",
      ampliarAria: "Enlarge the page to read it more easily",
      ampliarTitle: "Enlarge the page",
      preparando: "Preparing the menu…",
      libroAria: "Digital menu, book of pages",
      pista: "Drag the corner of the page · use ← → · tap <b>Zoom in</b> to read closely",
      visorAria: "Enlarged page of the menu",
      cerrarAria: "Close and return to the book",
      cerrarTitle: "Close (Esc)",
      anteriorAria: "Previous page",
      anteriorTitle: "Previous page (←)",
      siguienteAria: "Next page",
      siguienteTitle: "Next page (→)",
      alejarAria: "Zoom out",
      acercarAria: "Zoom in",
      normalAria: "Normal size",
      pistaVisor: "Pinch or double-tap to zoom · drag to move",
      pagina: "Page",
      de: "of",
      altPagina: function (n) { return "Menu page " + n; },
      altPaginaAmpliada: function (n) { return "Menu page " + n + ", enlarged"; }
    }
  };

  var idioma = "es";

  var libroEl = document.getElementById("libro");
  var libroMarcoEl = libroEl.parentNode;
  var overlay = document.getElementById("cargando");
  var overlayTexto = overlay ? overlay.querySelector("p") : null;
  var lemaEl = document.getElementById("lema");
  var pistaEl = document.getElementById("pista");
  var btnZoomTexto = document.getElementById("btn-zoom-texto");
  var btnIdiomaEs = document.getElementById("btn-idioma-es");
  var btnIdiomaEn = document.getElementById("btn-idioma-en");
  var paginaActualEl = document.getElementById("pagina-actual");
  var paginaTotalEl = document.getElementById("pagina-total");
  var barraEl = document.getElementById("barra-progreso");
  var btnPrev = document.getElementById("btn-prev");
  var btnNext = document.getElementById("btn-next");
  var btnZoom = document.getElementById("btn-zoom");

  var visor = document.getElementById("visor");
  var visorLienzo = document.getElementById("visor-lienzo");
  var visorImg = document.getElementById("visor-img");
  var visorTitulo = document.getElementById("visor-titulo");
  var visorCerrar = document.getElementById("visor-cerrar");
  var visorAnterior = document.getElementById("visor-anterior");
  var visorSiguiente = document.getElementById("visor-siguiente");
  var visorMas = document.getElementById("visor-mas");
  var visorMenos = document.getElementById("visor-menos");
  var visorReset = document.getElementById("visor-reset");
  var visorPista = document.getElementById("visor-pista");

  var pageFlip = null;
  var modoRetrato = null;
  var totalPaginas = 0;
  var rutasPaginas = [];

  var ESCALA_MIN = 1;
  var ESCALA_MAX = 4;
  var escala = 1;
  var panX = 0;
  var panY = 0;
  var indiceVisor = 0;
  var punteros = new Map();
  var toques = new Map();
  var distanciaInicial = 0;
  var escalaInicial = 1;
  var ultimoToque = 0;
  var huboArrastre = false;
  var huboPellizco = false;

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

  function marcarIdioma() {
    if (btnIdiomaEs) btnIdiomaEs.setAttribute("aria-pressed", idioma === "es" ? "true" : "false");
    if (btnIdiomaEn) btnIdiomaEn.setAttribute("aria-pressed", idioma === "en" ? "true" : "false");
  }

  function aplicarTextos() {
    var t = TEXTOS[idioma];
    document.documentElement.lang = idioma;
    document.title = t.titulo;

    if (lemaEl) lemaEl.textContent = t.lema;
    if (pistaEl) pistaEl.innerHTML = t.pista;
    if (overlayTexto) overlayTexto.textContent = t.preparando;

    btnZoom.setAttribute("aria-label", t.ampliarAria);
    btnZoom.title = t.ampliarTitle;
    if (btnZoomTexto) btnZoomTexto.textContent = t.ampliar;

    libroEl.setAttribute("aria-label", t.libroAria);
    visor.setAttribute("aria-label", t.visorAria);

    visorCerrar.setAttribute("aria-label", t.cerrarAria);
    visorCerrar.title = t.cerrarTitle;
    visorAnterior.setAttribute("aria-label", t.anteriorAria);
    visorAnterior.title = t.anteriorTitle;
    visorSiguiente.setAttribute("aria-label", t.siguienteAria);
    visorSiguiente.title = t.siguienteTitle;
    visorMenos.setAttribute("aria-label", t.alejarAria);
    visorMas.setAttribute("aria-label", t.acercarAria);
    visorReset.setAttribute("aria-label", t.normalAria);
    if (visorPista) visorPista.textContent = t.pistaVisor;
  }

  function idiomaInicial() {
    var parametro = null;
    try {
      parametro = new URLSearchParams(window.location.search).get("idioma");
    } catch (error) {
      parametro = null;
    }
    if (parametro === "es" || parametro === "en") return parametro;
    try {
      var guardado = window.localStorage.getItem(CLAVE_IDIOMA);
      if (guardado === "es" || guardado === "en") return guardado;
    } catch (error) {
      /* almacenamiento no disponible */
    }
    return "es";
  }

  async function cambiarIdioma(nuevo, guardar) {
    if (nuevo !== "es" && nuevo !== "en") return;
    if (nuevo === idioma && rutasPaginas.length) return;

    if (nuevo === "en" && !(await existeImagen(RUTA_PAGINAS_EN + "01.webp"))) {
      marcarIdioma();
      return;
    }

    var indice = 0;
    try {
      if (pageFlip && typeof pageFlip.getCurrentPageIndex === "function") {
        indice = pageFlip.getCurrentPageIndex() || 0;
      }
    } catch (error) {
      indice = 0;
    }

    idioma = nuevo;
    RUTA_PAGINAS = idioma === "en" ? RUTA_PAGINAS_EN : RUTA_PAGINAS_ES;
    if (guardar !== false) {
      try {
        window.localStorage.setItem(CLAVE_IDIOMA, idioma);
      } catch (error) {
        /* almacenamiento no disponible */
      }
    }
    marcarIdioma();
    aplicarTextos();

    var rutas = await descubrirPaginas();
    if (!rutas.length) return;
    totalPaginas = rutas.length;
    rutasPaginas = rutas;
    montarLibro();

    var destino = Math.min(indice, totalPaginas - 1);
    if (destino > 0 && pageFlip) {
      pageFlip.turnToPage(destino);
      pintarProgreso(destino);
    }
  }

  function crearPaginas(rutas) {
    libroEl.innerHTML = "";
    var fragmento = document.createDocumentFragment();
    rutas.forEach(function (ruta, indice) {
      var hoja = document.createElement("div");
      hoja.className = "page" + (indice === 0 ? " page--tapa" : "");
      var img = document.createElement("img");
      img.src = ruta;
      img.alt = TEXTOS[idioma].altPagina(indice + 1);
      img.decoding = "async";
      img.draggable = false;
      hoja.appendChild(img);
      fragmento.appendChild(hoja);
    });
    libroEl.appendChild(fragmento);
  }

  function predecodificarPaginas() {
    var imagenes = libroEl.querySelectorAll("img");
    for (var i = 0; i < imagenes.length; i++) {
      var img = imagenes[i];
      if (typeof img.decode !== "function") continue;
      var pendiente = img.decode();
      if (pendiente && typeof pendiente.catch === "function") {
        pendiente.catch(function () {});
      }
    }
  }

  function montarLibro() {
    if (!rutasPaginas.length) return;

    if (pageFlip) {
      pageFlip.destroy();
      pageFlip = null;
    }

    if (!libroEl.isConnected && libroMarcoEl) {
      libroMarcoEl.appendChild(libroEl);
    }

    libroEl.className = "libro";
    libroEl.style.cssText = "";
    crearPaginas(rutasPaginas);

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
    btnZoom.disabled = false;
    if (overlay) overlay.classList.add("oculto");

    /* Decodifica las hojas en segundo plano para que el primer volteo no
       pague la decodificacion de la imagen. */
    window.setTimeout(predecodificarPaginas, 60);
  }

  function pintarProgreso(indice) {
    var actual = Math.min(totalPaginas, Math.max(1, indice + 1));
    paginaActualEl.textContent = String(actual);
    paginaTotalEl.textContent = String(totalPaginas);
    barraEl.style.width = (actual / totalPaginas) * 100 + "%";
    btnPrev.disabled = actual <= 1;
    btnNext.disabled = actual >= totalPaginas;
  }

  /* ---------- ampliar la página ---------- */

  function fijarVista() {
    visorImg.style.transform =
      "translate3d(" + panX + "px," + panY + "px,0) scale(" + escala + ")";
    visorReset.textContent = Math.round(escala * 100) + "%";
    visorMenos.disabled = escala <= ESCALA_MIN + 0.001;
    visorMas.disabled = escala >= ESCALA_MAX - 0.001;
    visorAnterior.disabled = indiceVisor <= 0;
    visorSiguiente.disabled = indiceVisor >= totalPaginas - 1;
  }

  function limitarPan() {
    var caja = visorLienzo.getBoundingClientRect();
    var maxX = Math.max(0, (visorImg.offsetWidth * escala - caja.width) / 2);
    var maxY = Math.max(0, (visorImg.offsetHeight * escala - caja.height) / 2);
    panX = Math.min(maxX, Math.max(-maxX, panX));
    panY = Math.min(maxY, Math.max(-maxY, panY));
  }

  function fijarEscala(nueva) {
    escala = Math.min(ESCALA_MAX, Math.max(ESCALA_MIN, nueva));
    if (escala <= ESCALA_MIN) {
      panX = 0;
      panY = 0;
    }
    limitarPan();
    fijarVista();
  }

  function cargarPagina(indice) {
    if (!rutasPaginas.length) return;
    var t = TEXTOS[idioma];
    indiceVisor = Math.min(rutasPaginas.length - 1, Math.max(0, indice));
    visorImg.src = rutasPaginas[indiceVisor];
    visorImg.alt = t.altPaginaAmpliada(indiceVisor + 1);
    visorTitulo.textContent = t.pagina + " " + (indiceVisor + 1) + " " + t.de + " " + totalPaginas;
    escala = 1;
    panX = 0;
    panY = 0;
    fijarVista();
  }

  function abrirVisor() {
    if (!totalPaginas) return;
    var indice = 0;
    try {
      if (pageFlip && typeof pageFlip.getCurrentPageIndex === "function") {
        indice = pageFlip.getCurrentPageIndex() || 0;
      }
    } catch (error) {
      indice = 0;
    }
    cargarPagina(indice);
    visor.hidden = false;
    visor.setAttribute("aria-hidden", "false");
    document.body.classList.add("con-visor");
    visorCerrar.focus();
  }

  function cerrarVisor() {
    if (visor.hidden) return;
    visor.hidden = true;
    visor.setAttribute("aria-hidden", "true");
    document.body.classList.remove("con-visor");
    punteros.clear();
    toques.clear();
    btnZoom.focus();
  }

  /* ---------- gestos (ratón/lápiz y dedos) ---------- */

  function distanciaMapa(mapa) {
    var valores = Array.from(mapa.values());
    if (valores.length < 2) return 0;
    var dx = valores[0].x - valores[1].x;
    var dy = valores[0].y - valores[1].y;
    return Math.hypot(dx, dy);
  }

  function iniciarContacto(mapa, id, x, y) {
    mapa.set(id, { x: x, y: y });
    if (mapa.size === 1) {
      huboArrastre = false;
      huboPellizco = false;
      distanciaInicial = 0;
      escalaInicial = escala;
    } else if (mapa.size === 2) {
      huboPellizco = true;
      distanciaInicial = distanciaMapa(mapa);
      escalaInicial = escala;
    }
  }

  function moverContacto(mapa, id, x, y) {
    var previo = mapa.get(id);
    if (!previo) return;
    mapa.set(id, { x: x, y: y });

    if (mapa.size >= 2) {
      var distancia = distanciaMapa(mapa);
      if (distanciaInicial > 0 && distancia > 0) {
        fijarEscala(escalaInicial * (distancia / distanciaInicial));
      }
      return;
    }

    if (escala > 1) {
      panX += x - previo.x;
      panY += y - previo.y;
      if (Math.abs(x - previo.x) + Math.abs(y - previo.y) > 2) huboArrastre = true;
      limitarPan();
      fijarVista();
      visorLienzo.classList.add("arrastrando");
    }
  }

  function terminarContacto(mapa, id, esToque) {
    mapa.delete(id);
    if (mapa.size < 2) distanciaInicial = 0;
    visorLienzo.classList.remove("arrastrando");

    if (huboArrastre || huboPellizco) {
      ultimoToque = 0;
      return;
    }
    if (!esToque || mapa.size !== 0) return;

    var ahora = Date.now();
    if (ahora - ultimoToque < 300) {
      fijarEscala(escala > 1.2 ? 1 : 2.5);
      ultimoToque = 0;
    } else {
      ultimoToque = ahora;
    }
  }

  /* Dedos: se usan Touch Events porque Safari en iOS no entrega pointermove
     de forma fiable y emite pointercancel en mitad del gesto. */
  visorLienzo.addEventListener("touchstart", function (evento) {
    evento.preventDefault();
    if (evento.touches.length > 2) {
      toques.clear();
      return;
    }
    for (var i = 0; i < evento.changedTouches.length; i++) {
      var toque = evento.changedTouches[i];
      iniciarContacto(toques, toque.identifier, toque.clientX, toque.clientY);
    }
  }, { passive: false });

  visorLienzo.addEventListener("touchmove", function (evento) {
    evento.preventDefault();
    if (!toques.size) return;
    for (var i = 0; i < evento.changedTouches.length; i++) {
      var toque = evento.changedTouches[i];
      moverContacto(toques, toque.identifier, toque.clientX, toque.clientY);
    }
  }, { passive: false });

  visorLienzo.addEventListener("touchend", function (evento) {
    evento.preventDefault();
    for (var i = 0; i < evento.changedTouches.length; i++) {
      terminarContacto(toques, evento.changedTouches[i].identifier, true);
    }
  }, { passive: false });

  visorLienzo.addEventListener("touchcancel", function (evento) {
    for (var i = 0; i < evento.changedTouches.length; i++) {
      toques.delete(evento.changedTouches[i].identifier);
    }
    distanciaInicial = 0;
    visorLienzo.classList.remove("arrastrando");
  });

  /* Ratón y lápiz: Pointer Events. El dedo ya lo atienden los Touch Events. */
  visorLienzo.addEventListener("pointerdown", function (evento) {
    if (evento.pointerType === "touch") return;
    try {
      visorLienzo.setPointerCapture(evento.pointerId);
    } catch (error) {
      /* iOS/Safari puede rechazar la captura; el gesto sigue funcionando. */
    }
    iniciarContacto(punteros, evento.pointerId, evento.clientX, evento.clientY);
  });

  visorLienzo.addEventListener("pointermove", function (evento) {
    if (evento.pointerType === "touch") return;
    moverContacto(punteros, evento.pointerId, evento.clientX, evento.clientY);
  });

  visorLienzo.addEventListener("pointerup", function (evento) {
    if (evento.pointerType === "touch") return;
    terminarContacto(punteros, evento.pointerId, false);
  });

  visorLienzo.addEventListener("pointercancel", function (evento) {
    if (evento.pointerType === "touch") return;
    terminarContacto(punteros, evento.pointerId, false);
  });

  visorLienzo.addEventListener("wheel", function (evento) {
    evento.preventDefault();
    fijarEscala(escala * (evento.deltaY < 0 ? 1.15 : 1 / 1.15));
  }, { passive: false });

  btnZoom.addEventListener("click", abrirVisor);
  visorCerrar.addEventListener("click", cerrarVisor);
  visorMas.addEventListener("click", function () { fijarEscala(escala * 1.35); });
  visorMenos.addEventListener("click", function () { fijarEscala(escala / 1.35); });
  visorReset.addEventListener("click", function () { fijarEscala(1); });
  visorAnterior.addEventListener("click", function () { cargarPagina(indiceVisor - 1); });
  visorSiguiente.addEventListener("click", function () { cargarPagina(indiceVisor + 1); });
  visorImg.addEventListener("load", function () { limitarPan(); fijarVista(); });

  document.addEventListener("keydown", function (evento) {
    if (visor.hidden) return;
    if (evento.key === "Escape") {
      evento.preventDefault();
      cerrarVisor();
    } else if (evento.key === "+" || evento.key === "=") {
      evento.preventDefault();
      fijarEscala(escala * 1.35);
    } else if (evento.key === "-" || evento.key === "_") {
      evento.preventDefault();
      fijarEscala(escala / 1.35);
    } else if (evento.key === "0") {
      evento.preventDefault();
      fijarEscala(1);
    } else if (evento.key === "ArrowLeft") {
      evento.preventDefault();
      cargarPagina(indiceVisor - 1);
    } else if (evento.key === "ArrowRight") {
      evento.preventDefault();
      cargarPagina(indiceVisor + 1);
    }
  });

  function siguiente() {
    if (pageFlip) pageFlip.flipNext();
  }

  function anterior() {
    if (pageFlip) pageFlip.flipPrev();
  }

  btnNext.addEventListener("click", siguiente);
  btnPrev.addEventListener("click", anterior);

  if (btnIdiomaEs) {
    btnIdiomaEs.addEventListener("click", function () { cambiarIdioma("es", true); });
  }
  if (btnIdiomaEn) {
    btnIdiomaEn.addEventListener("click", function () { cambiarIdioma("en", true); });
  }

  document.addEventListener("keydown", function (e) {
    if (!visor.hidden) return;
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
    if (modoRetrato === null) return;
    var nuevoModo = window.innerWidth < BREAKPOINT_MOVIL;
    if (nuevoModo === modoRetrato) return;
    clearTimeout(temporizadorResize);
    temporizadorResize = setTimeout(function () {
      montarLibro();
    }, 250);
  });

  async function iniciar() {
    idioma = idiomaInicial();
    RUTA_PAGINAS = idioma === "en" ? RUTA_PAGINAS_EN : RUTA_PAGINAS_ES;

    if (idioma === "en" && !(await existeImagen(RUTA_PAGINAS_EN + "01.webp"))) {
      idioma = "es";
      RUTA_PAGINAS = RUTA_PAGINAS_ES;
    }

    marcarIdioma();
    aplicarTextos();

    var rutas = await descubrirPaginas();

    if (!rutas.length) {
      if (overlay) {
        overlay.innerHTML = idioma === "en"
          ? '<p style="max-width:340px;text-align:center">No page images found.<br>' +
            "Place <b>01.webp</b>, <b>02.webp</b>, <b>03.webp</b>… inside the <b>paginas/</b> folder.</p>"
          : '<p style="max-width:340px;text-align:center">No encontré imágenes.<br>' +
            "Coloca <b>01.webp</b>, <b>02.webp</b>, <b>03.webp</b>… dentro de la carpeta <b>paginas/</b>.</p>";
      }
      return;
    }

    totalPaginas = rutas.length;
    rutasPaginas = rutas;
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
