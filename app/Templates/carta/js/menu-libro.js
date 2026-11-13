(function () {
  "use strict";

  var RUTA_PAGINAS = "paginas/";
  var EXTENSIONES = ["webp", "jpg", "jpeg", "png"];
  var MAX_PAGINAS = 40;
  var BREAKPOINT_MOVIL = 820;

  var libroEl = document.getElementById("libro");
  var libroMarcoEl = libroEl.parentNode;
  var overlay = document.getElementById("cargando");
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

  function crearPaginas(rutas) {
    libroEl.innerHTML = "";
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
    indiceVisor = Math.min(rutasPaginas.length - 1, Math.max(0, indice));
    visorImg.src = rutasPaginas[indiceVisor];
    visorImg.alt = "Página " + (indiceVisor + 1) + " del menú, ampliada";
    visorTitulo.textContent = "Página " + (indiceVisor + 1) + " de " + totalPaginas;
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
    btnZoom.focus();
  }

  function distanciaPunteros() {
    var valores = Array.from(punteros.values());
    if (valores.length < 2) return 0;
    var dx = valores[0].x - valores[1].x;
    var dy = valores[0].y - valores[1].y;
    return Math.hypot(dx, dy);
  }

  visorLienzo.addEventListener("pointerdown", function (evento) {
    visorLienzo.setPointerCapture(evento.pointerId);
    punteros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
    huboArrastre = false;
    if (punteros.size === 1) huboPellizco = false;
    if (punteros.size === 2) {
      huboPellizco = true;
      distanciaInicial = distanciaPunteros();
      escalaInicial = escala;
    }
  });

  visorLienzo.addEventListener("pointermove", function (evento) {
    var previo = punteros.get(evento.pointerId);
    if (!previo) return;
    punteros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });

    if (punteros.size >= 2) {
      var distancia = distanciaPunteros();
      if (distanciaInicial > 0 && distancia > 0) {
        fijarEscala(escalaInicial * (distancia / distanciaInicial));
      }
      return;
    }

    if (escala > 1) {
      panX += evento.clientX - previo.x;
      panY += evento.clientY - previo.y;
      if (Math.abs(evento.clientX - previo.x) + Math.abs(evento.clientY - previo.y) > 2) {
        huboArrastre = true;
      }
      limitarPan();
      fijarVista();
      visorLienzo.classList.add("arrastrando");
    }
  });

  function soltarPuntero(evento) {
    punteros.delete(evento.pointerId);
    if (punteros.size < 2) distanciaInicial = 0;
    visorLienzo.classList.remove("arrastrando");

    if (evento.pointerType === "touch" && !huboArrastre && !huboPellizco && punteros.size === 0) {
      var ahora = Date.now();
      if (ahora - ultimoToque < 300) {
        fijarEscala(escala > 1.2 ? 1 : 2.5);
        ultimoToque = 0;
      } else {
        ultimoToque = ahora;
      }
    }
  }

  visorLienzo.addEventListener("pointerup", soltarPuntero);
  visorLienzo.addEventListener("pointercancel", soltarPuntero);

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
