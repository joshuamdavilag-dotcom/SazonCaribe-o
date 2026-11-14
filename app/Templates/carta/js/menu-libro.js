(function () {
  "use strict";

  /* La carta se dibuja en el navegador con los datos reales de la API
     pública (/api/public). No hay imágenes de páginas fijas: cualquier
     alta, baja o cambio hecho en Gestión de Menú aparece al recargar. */

  var API_PUBLICA = "/api/public";
  var BREAKPOINT_MOVIL = 820;
  var CLAVE_IDIOMA = "carta_idioma";

  /* Lienzo de diseño de cada hoja (se escala al tamaño real de la página). */
  var ANCHO_HOJA = 1200;
  var ALTO_HOJA = 1800;

  var MAX_FOTOS_SIMULTANEAS = 4;

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
      alternarAria: "Idioma de la carta",
      altPagina: function (n) { return "Página " + n + " del menú"; },
      altPaginaAmpliada: function (n) { return "Página " + n + " del menú, ampliada"; },
      portadaTitulo: "MENÚ",
      portadaPie: "NICARAGUA  ·  C$  ·  COCINA CARIBEÑA",
      gracias1: "Gracias por",
      gracias2: "su visita",
      contraPie: "PREGUNTE A SU MESERO POR LAS ESPECIALIDADES DEL DÍA",
      extrasSub: "Todos los acompañamientos, en C$",
      errorCarga: "No se pudo cargar el menú. Revisa la conexión e inténtalo de nuevo.",
      menuVacio: "El menú está vacío. Agrega platillos en Gestión de Menú.",
      reintentar: "Reintentar"
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
      alternarAria: "Menu language",
      altPagina: function (n) { return "Menu page " + n; },
      altPaginaAmpliada: function (n) { return "Menu page " + n + ", enlarged"; },
      portadaTitulo: "MENU",
      portadaPie: "NICARAGUA  ·  C$  ·  CARIBBEAN CUISINE",
      gracias1: "Thank you for",
      gracias2: "your visit",
      contraPie: "ASK YOUR SERVER ABOUT TODAY'S SPECIALS",
      extrasSub: "All sides, in C$",
      errorCarga: "The menu could not be loaded. Check your connection and try again.",
      menuVacio: "The menu is empty. Add dishes in Menu Management.",
      reintentar: "Try again"
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
  var visorHoja = document.getElementById("visor-hoja");
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
  var medidorEl = null;
  var observador = null;

  var estado = {
    menu: [],
    categorias: [],
    grupos: [],
    hojas: [],
    paginas: [],
    total: 0
  };
  var paginasDom = [];

  var colaFotos = [];
  var fotosEnCurso = 0;
  var generacionFotos = 0;

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

  /* ---------- textos e idioma ---------- */

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
    if (overlayTexto && overlayTexto.isConnected) overlayTexto.textContent = t.preparando;

    btnZoom.setAttribute("aria-label", t.ampliarAria);
    btnZoom.title = t.ampliarTitle;
    if (btnZoomTexto) btnZoomTexto.textContent = t.ampliar;

    libroEl.setAttribute("aria-label", t.libroAria);
    visor.setAttribute("aria-label", t.visorAria);
    var idiomas = document.querySelector(".idiomas");
    if (idiomas) idiomas.setAttribute("aria-label", t.alternarAria);

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

  /* ---------- datos ---------- */

  async function cargarMenu() {
    var respuestas = await Promise.all([
      fetch(API_PUBLICA + "/menu", { cache: "no-store" }),
      fetch(API_PUBLICA + "/categories", { cache: "no-store" })
    ]);
    if (!respuestas[0].ok || !respuestas[1].ok) {
      throw new Error("respuesta " + respuestas[0].status + "/" + respuestas[1].status);
    }
    var menu = await respuestas[0].json();
    var categorias = await respuestas[1].json();
    return {
      menu: Array.isArray(menu) ? menu : [],
      categorias: Array.isArray(categorias) ? categorias : []
    };
  }

  function agrupar(menu, categorias) {
    var grupos = [];
    var porId = {};

    categorias.forEach(function (cat) {
      var grupo = {
        id: cat.id,
        nombre: cat.nombre || "",
        nombre_en: cat.nombre_en || null,
        items: []
      };
      porId[cat.id] = grupo;
      grupos.push(grupo);
    });

    menu.forEach(function (item) {
      var cat = item.categoria || {};
      var id = cat.id != null ? cat.id : null;
      var grupo = id != null ? porId[id] : null;
      if (!grupo) {
        var clave = id != null ? id : "suelto";
        grupo = porId[clave];
        if (!grupo) {
          grupo = {
            id: id,
            nombre: cat.nombre || "Menú",
            nombre_en: cat.nombre_en || null,
            items: []
          };
          porId[clave] = grupo;
          grupos.push(grupo);
        }
      }
      grupo.items.push(item);
    });

    grupos = grupos.filter(function (g) { return g.items.length > 0; });

    /* Orden de la carta impresa: entradas primero, acompañamientos al final.
       Las categorías nuevas (sin posición conocida) van antes de Extras. */
    grupos.sort(function (a, b) {
      return pesoCategoria(a.nombre) - pesoCategoria(b.nombre);
    });

    grupos.forEach(function (g) {
      g.items.sort(function (a, b) {
        return String(a.nombre || "").localeCompare(String(b.nombre || ""), "es", { sensitivity: "base" });
      });
    });

    return grupos;
  }

  var ORDEN_CATEGORIAS = [
    "entradas",
    "sopas",
    "platos ejecutivos",
    "antojitos",
    "platos fuertes",
    "para compartir",
    "zona caribena",
    "bebidas",
    "postres",
    "cafe",
    "extras"
  ];

  function limpiar(texto) {
    return String(texto == null ? "" : texto)
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{2B00}-\u{2BFF}]/gu, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function normalizar(texto) {
    return limpiar(texto)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function pesoCategoria(nombre) {
    var clave = normalizar(nombre);
    var posicion = ORDEN_CATEGORIAS.indexOf(clave);
    if (posicion !== -1) return posicion;
    if (clave.indexOf("extra") !== -1 || clave.indexOf("acompan") !== -1) return 90;
    return 50;
  }

  function nombreItem(item) {
    var es = limpiar(item.nombre);
    if (idioma === "en") {
      var en = limpiar(item.nombre_en);
      if (en) return en;
    }
    return es;
  }

  function descripcionItem(item) {
    var es = limpiar(item.descripcion);
    if (idioma === "en") {
      var en = limpiar(item.descripcion_en);
      if (en) return en;
      /* Plato traducido pero sin descripción en inglés: no se mezcla el
         texto en español debajo de un nombre en inglés. */
      if (limpiar(item.nombre_en)) return "";
    }
    return es;
  }

  function nombreCategoria(grupo) {
    if (idioma === "en" && limpiar(grupo.nombre_en)) return limpiar(grupo.nombre_en);
    return limpiar(grupo.nombre);
  }

  function moneda(precio) {
    var numero = Number(precio);
    if (!isFinite(numero)) return "C$" + precio;
    var partes = numero.toFixed(2).split(".");
    partes[0] = partes[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return "C$" + partes.join(".");
  }

  /* ---------- fotos (carga progresiva) ---------- */

  /* La cola se llena mientras las hojas se construyen (todavia dentro del
     medidor). Al pasar las hojas a las paginas quedan desconectadas un
     instante; una celda desconectada NO se descarta: se devuelve al final y
     se reintenta cuando el libro ya esta montado. Descartarlas dejaba 44 de
     57 fotos sin cargar. */
  function procesarColaFotos() {
    var saltadas = 0;
    while (fotosEnCurso < MAX_FOTOS_SIMULTANEAS && colaFotos.length > 0) {
      var celda = colaFotos.shift();
      var url = celda.getAttribute("data-foto");
      var img = celda.querySelector("img");
      if (!url || !img || celda.classList.contains("con-foto")) {
        saltadas = 0;
        continue;
      }
      if (!celda.isConnected) {
        colaFotos.push(celda);
        saltadas += 1;
        if (saltadas >= colaFotos.length) break;
        continue;
      }
      saltadas = 0;
      iniciarFoto(celda, img, url);
    }
  }

  function iniciarFoto(celda, img, url) {
    celda.removeAttribute("data-foto");
    fotosEnCurso += 1;

    var generacion = generacionFotos;
    var terminar = function (cargada) {
      if (generacion !== generacionFotos) return;
      fotosEnCurso = Math.max(0, fotosEnCurso - 1);
      if (cargada) celda.classList.add("con-foto");
      procesarColaFotos();
    };

    img.onload = function () { terminar(true); };
    img.onerror = function () {
      /* Un reintento con cache aparte: los CDN de imagenes fallan de forma
         transitoria y antes la foto quedaba en blanco para siempre. */
      if (!celda.hasAttribute("data-reintento")) {
        celda.setAttribute("data-reintento", "1");
        celda.setAttribute(
          "data-foto",
          url + (url.indexOf("?") === -1 ? "?" : "&") + "reintento=1"
        );
        if (generacion === generacionFotos) {
          fotosEnCurso = Math.max(0, fotosEnCurso - 1);
          img.removeAttribute("src");
          procesarColaFotos();
        }
        return;
      }
      terminar(false);
    };
    img.src = url;
  }

  function encolarFoto(celda) {
    colaFotos.push(celda);
    procesarColaFotos();
  }

  function limpiarColaFotos() {
    generacionFotos += 1;
    colaFotos = [];
    fotosEnCurso = 0;
  }

  function priorizarFotos(indice) {
    if (!paginasDom.length) return;
    [indice, indice + 1, indice + 2, indice - 1].forEach(function (i) {
      var pagina = paginasDom[i];
      if (!pagina) return;
      var pendientes = pagina.querySelectorAll("[data-foto]");
      for (var j = pendientes.length - 1; j >= 0; j--) {
        colaFotos.unshift(pendientes[j]);
      }
    });
    procesarColaFotos();
  }

  function forzarFoto(celda) {
    var url = celda.getAttribute("data-foto");
    var img = celda.querySelector("img");
    celda.removeAttribute("data-foto");
    if (!url || !img) return;
    img.onload = function () { celda.classList.add("con-foto"); };
    img.onerror = function () { celda.classList.remove("con-foto"); };
    img.src = url;
  }

  function forzarFotosDe(raiz) {
    var pendientes = raiz.querySelectorAll("[data-foto]");
    for (var i = 0; i < pendientes.length; i++) forzarFoto(pendientes[i]);
  }

  /* ---------- construcción de hojas ---------- */

  function obtenerMedidor() {
    if (!medidorEl) {
      medidorEl = document.createElement("div");
      medidorEl.className = "medidor";
      medidorEl.setAttribute("aria-hidden", "true");
      document.body.appendChild(medidorEl);
    }
    return medidorEl;
  }

  function crearCeldaFoto(item, clase) {
    var celda = document.createElement("div");
    celda.className = clase;

    var inicial = document.createElement("span");
    inicial.className = "h-inicial";
    var nombre = nombreItem(item);
    inicial.textContent = (nombre || "?").charAt(0).toUpperCase();
    celda.appendChild(inicial);

    if (item.imagen_url) {
      var img = document.createElement("img");
      img.alt = "";
      img.decoding = "async";
      img.draggable = false;
      celda.appendChild(img);
      celda.setAttribute("data-foto", item.imagen_url);
      if (clase === "h-foto") encolarFoto(celda);
    }
    return celda;
  }

  function filaFoto(item) {
    var fila = document.createElement("div");
    fila.className = "h-fila";

    fila.appendChild(crearCeldaFoto(item, "h-foto"));

    var texto = document.createElement("div");
    texto.className = "h-texto";

    var nombre = document.createElement("div");
    nombre.className = "h-nombre";
    nombre.textContent = nombreItem(item);
    texto.appendChild(nombre);

    var descripcion = descripcionItem(item);
    if (descripcion) {
      var desc = document.createElement("div");
      desc.className = "h-desc";
      desc.textContent = descripcion;
      texto.appendChild(desc);
    }

    fila.appendChild(texto);

    var precio = document.createElement("div");
    precio.className = "h-precio";
    precio.textContent = moneda(item.precio);
    fila.appendChild(precio);

    return fila;
  }

  function filaCompacta(item) {
    var fila = document.createElement("div");
    fila.className = "h-item";

    var nombre = document.createElement("span");
    nombre.className = "h-item-nombre";
    nombre.textContent = nombreItem(item);

    var puntos = document.createElement("span");
    puntos.className = "h-item-puntos";

    var precio = document.createElement("span");
    precio.className = "h-item-precio";
    precio.textContent = moneda(item.precio);

    fila.appendChild(nombre);
    fila.appendChild(puntos);
    fila.appendChild(precio);
    return fila;
  }

  function crearSubtitulo(titulo) {
    var sub = document.createElement("div");
    sub.className = "h-subtitulo";
    sub.textContent = titulo;
    return sub;
  }

  function nuevaHojaContenido(titulo, subtitulo) {
    var hoja = document.createElement("div");
    hoja.className = "hoja";

    var cab = document.createElement("div");
    cab.className = "h-cab";

    var marca = document.createElement("div");
    marca.className = "h-marca";
    marca.textContent = "SAZÓN CARIBEÑO";
    cab.appendChild(marca);

    var h2 = document.createElement("h2");
    h2.className = "h-titulo";
    h2.textContent = titulo;
    cab.appendChild(h2);

    var regla = document.createElement("div");
    regla.className = "h-regla";
    regla.appendChild(document.createElement("i"));
    regla.appendChild(document.createElement("i"));
    cab.appendChild(regla);

    if (subtitulo) {
      var sub = document.createElement("div");
      sub.className = "h-sub";
      sub.textContent = subtitulo;
      cab.appendChild(sub);
    }

    var cuerpo = document.createElement("div");
    cuerpo.className = "h-cuerpo";

    var pie = document.createElement("div");
    pie.className = "h-pie";
    var filaPie = document.createElement("div");
    filaPie.className = "h-pie-fila";
    var marcaPie = document.createElement("span");
    marcaPie.className = "h-pie-marca";
    marcaPie.textContent = "SAZÓN CARIBEÑO";
    var numero = document.createElement("span");
    numero.className = "h-pie-num";
    filaPie.appendChild(marcaPie);
    filaPie.appendChild(numero);
    pie.appendChild(filaPie);

    hoja.appendChild(cab);
    hoja.appendChild(cuerpo);
    hoja.appendChild(pie);
    return hoja;
  }

  function sobrepasa(cuerpo) {
    return cuerpo.scrollHeight > cuerpo.clientHeight + 1;
  }

  var CATEGORIAS_SIN_FOTO = ["bebida", "extra", "acompan"];

  function usaListaCompacta(items, nombre) {
    var clave = normalizar(nombre);
    for (var i = 0; i < CATEGORIAS_SIN_FOTO.length; i++) {
      if (clave.indexOf(CATEGORIAS_SIN_FOTO[i]) !== -1) return true;
    }
    var conFoto = 0;
    items.forEach(function (item) { if (item.imagen_url) conFoto += 1; });
    return conFoto * 2 < items.length;
  }

  /* Cuantos renglones caben de verdad en una hoja. Se mide con el mismo
     constructor de filas que usa la carta, asi que respeta tipografia,
     alto de foto y el espacio del pie. */
  function medirCapacidad(compacta) {
    var hoja = nuevaHojaContenido("Medida", null);
    obtenerMedidor().appendChild(hoja);

    var cuerpo = hoja.querySelector(".h-cuerpo");
    var contenedor = cuerpo;
    if (compacta) {
      contenedor = document.createElement("div");
      contenedor.className = "h-lista";
      cuerpo.appendChild(contenedor);
    }

    /* Muestra de peor caso: nombre en dos lineas y descripcion en dos. */
    var muestra = {
      nombre: "Nombre de platillo bastante largo para partirse",
      descripcion: "Descripcion de ejemplo con el largo tipico de la carta para medir dos lineas.",
      precio: 100,
      imagen_url: null
    };

    var filas = 0;
    while (filas < 40) {
      var nodo = compacta ? filaCompacta(muestra) : filaFoto(muestra);
      contenedor.appendChild(nodo);
      if (sobrepasa(cuerpo)) {
        contenedor.removeChild(nodo);
        break;
      }
      filas += 1;
    }

    hoja.remove();
    return Math.max(1, filas);
  }

  function construirHojasContenido(grupos) {
    /* Las categorias sin foto (bebidas, extras) van como una sola lista
       continua: comparten hojas y solo se separan con un subtitulo. */
    var bloques = [];
    grupos.forEach(function (grupo) {
      var titulo = nombreCategoria(grupo);
      var compacta = usaListaCompacta(grupo.items, grupo.nombre);
      var anterior = bloques[bloques.length - 1];
      if (compacta && anterior && anterior.compacta) {
        anterior.partes.push({ titulo: titulo, items: grupo.items });
        return;
      }
      bloques.push({
        titulo: titulo,
        compacta: compacta,
        partes: [{ titulo: titulo, items: grupo.items }]
      });
    });

    var medidor = obtenerMedidor();
    var hojas = [];
    var capacidades = { fila: medirCapacidad(false), lista: medirCapacidad(true) };

    var indiceBloque = 0;
    while (indiceBloque < bloques.length) {
      var bloque = bloques[indiceBloque];
      var capacidad = bloque.compacta ? capacidades.lista : capacidades.fila;

      var filas = [];
      bloque.partes.forEach(function (parte, indiceParte) {
        var primeraDeParte = true;
        parte.items.forEach(function (item) {
          filas.push({ item: item, parte: indiceParte, primera: primeraDeParte });
          primeraDeParte = false;
        });
      });

      var total = filas.length;

      /* Reparto parejo: un platillo suelto en una hoja propia se ve como un
         error, asi que 9 platos van 5 + 4 y no 7 + 2. */
      var paginas = Math.ceil(total / capacidad);
      var porHoja = Math.ceil(total / paginas);

      var desde = 0;

      while (desde < total) {
        var corte = Math.min(total, desde + porHoja);
        var parteInicial = filas[desde].parte;
        var subtituloInicial = bloque.compacta && bloque.partes.length === 1 &&
          normalizar(bloque.titulo).indexOf("extra") !== -1
          ? TEXTOS[idioma].extrasSub
          : null;

        var hoja = nuevaHojaContenido(
          bloque.partes[parteInicial].titulo,
          parteInicial === 0 ? subtituloInicial : null
        );
        medidor.appendChild(hoja);

        var cuerpo = hoja.querySelector(".h-cuerpo");
        var contenedor = cuerpo;
        if (bloque.compacta) {
          contenedor = document.createElement("div");
          contenedor.className = "h-lista" + (total <= 3 ? " una" : "");
          cuerpo.appendChild(contenedor);
        }

        for (var k = desde; k < corte; k++) {
          var filaInfo = filas[k];
          if (filaInfo.primera && filaInfo.parte !== parteInicial) {
            contenedor.appendChild(crearSubtitulo(bloque.partes[filaInfo.parte].titulo));
          }
          contenedor.appendChild(
            bloque.compacta ? filaCompacta(filaInfo.item) : filaFoto(filaInfo.item)
          );
        }

        /* Red de seguridad: la medicion es del peor caso, pero si aun asi
           no cupiera se pasa el ultimo renglon a la hoja siguiente. */
        while (sobrepasa(cuerpo) && corte - desde > 1) {
          contenedor.removeChild(contenedor.lastChild);
          corte -= 1;
          if (contenedor.lastElementChild &&
              contenedor.lastElementChild.classList.contains("h-subtitulo")) {
            contenedor.removeChild(contenedor.lastElementChild);
          }
        }

        hojas.push(hoja);
        desde = corte;
        if (desde >= total) break;
      }

      /* Una seccion con foto se encadena bajo el subtitulo de la anterior
         solo si entra COMPLETA: nunca se parte despues de haberla anunciado. */
      if (bloque.compacta) {
        indiceBloque += 1;
        continue;
      }

      var ultima = hojas[hojas.length - 1];
      var cuerpoUltima = ultima.querySelector(".h-cuerpo");
      var contenedorUltima = cuerpoUltima.lastElementChild &&
        (cuerpoUltima.lastElementChild.classList.contains("h-lista"))
        ? cuerpoUltima.lastElementChild
        : cuerpoUltima;

      var siguienteIndice = indiceBloque + 1;
      while (siguienteIndice < bloques.length) {
        var siguiente = bloques[siguienteIndice];
        if (siguiente.compacta) break;
        if (siguiente.partes.length !== 1) break;
        if (siguiente.partes[0].items.length > capacidad) break;

        var subtitulo = crearSubtitulo(siguiente.titulo);
        var filasSiguiente = siguiente.partes[0].items.map(function (item) {
          return filaFoto(item);
        });

        contenedorUltima.appendChild(subtitulo);
        filasSiguiente.forEach(function (fila) { contenedorUltima.appendChild(fila); });

        if (sobrepasa(cuerpoUltima)) {
          contenedorUltima.removeChild(subtitulo);
          filasSiguiente.forEach(function (fila) { contenedorUltima.removeChild(fila); });
          break;
        }

        siguienteIndice += 1;
      }

      indiceBloque = siguienteIndice;
    }

    return hojas;
  }

  function fotosCandidatas(grupos) {
    var preferidas = ["zona caribe", "platos fuertes", "para compartir", "antojitos", "entradas"];
    var urls = [];
    var vistos = {};

    function agregar(item) {
      var url = item && item.imagen_url;
      if (!url || vistos[url]) return;
      vistos[url] = true;
      urls.push(url);
    }

    preferidas.forEach(function (clave) {
      grupos.forEach(function (grupo) {
        if (normalizar(grupo.nombre).indexOf(clave) === -1) return;
        grupo.items.forEach(agregar);
      });
    });
    grupos.forEach(function (grupo) { grupo.items.forEach(agregar); });

    return urls;
  }

  function elegirFotoPortada(grupos) {
    var urls = fotosCandidatas(grupos);
    return urls.length ? urls[0] : null;
  }

  function elegirFotoContra(grupos) {
    var urls = fotosCandidatas(grupos);
    if (urls.length > 1) return urls[1];
    return urls.length ? urls[0] : null;
  }

  function hojaPortada(grupos) {
    var t = TEXTOS[idioma];
    var hoja = document.createElement("div");
    hoja.className = "hoja hoja--portada";

    var marco = document.createElement("div");
    marco.className = "p-marco";
    marco.appendChild(crearCeldaFoto({ imagen_url: elegirFotoPortada(grupos), nombre: "S" }, "p-foto"));
    hoja.appendChild(marco);

    var marca = document.createElement("div");
    marca.className = "p-marca";
    marca.textContent = "SAZÓN CARIBEÑO";
    hoja.appendChild(marca);

    var titulo = document.createElement("div");
    titulo.className = "p-men";
    titulo.textContent = t.portadaTitulo;
    hoja.appendChild(titulo);

    var regla = document.createElement("div");
    regla.className = "p-regla";
    regla.appendChild(document.createElement("i"));
    regla.appendChild(document.createElement("i"));
    hoja.appendChild(regla);

    var lema = document.createElement("div");
    lema.className = "p-lema";
    lema.textContent = t.lema;
    hoja.appendChild(lema);

    var adorno = document.createElement("div");
    adorno.className = "p-adorno";
    adorno.appendChild(document.createElement("i"));
    adorno.appendChild(document.createElement("b"));
    adorno.appendChild(document.createElement("i"));
    hoja.appendChild(adorno);

    var pie = document.createElement("div");
    pie.className = "p-pie";
    pie.textContent = t.portadaPie;
    hoja.appendChild(pie);

    return hoja;
  }

  function hojaContra(grupos) {
    var t = TEXTOS[idioma];
    var foto = elegirFotoContra(grupos);

    var hoja = document.createElement("div");
    hoja.className = "hoja hoja--contra";
    if (foto) {
      hoja.style.backgroundImage =
        "linear-gradient(rgba(58,40,5,0.93), rgba(58,40,5,0.93)), url(\"" + foto + "\")";
      hoja.classList.add("con-foto-fondo");
    }

    var marco = document.createElement("div");
    marco.className = "c-marco";
    hoja.appendChild(marco);

    var marca = document.createElement("div");
    marca.className = "c-marca";
    marca.textContent = "SAZÓN CARIBEÑO";
    hoja.appendChild(marca);

    var gracias = document.createElement("div");
    gracias.className = "c-gracias";
    gracias.appendChild(document.createTextNode(t.gracias1));
    gracias.appendChild(document.createElement("br"));
    gracias.appendChild(document.createTextNode(t.gracias2));
    hoja.appendChild(gracias);

    var regla = document.createElement("div");
    regla.className = "c-regla";
    regla.appendChild(document.createElement("i"));
    regla.appendChild(document.createElement("i"));
    hoja.appendChild(regla);

    var lema = document.createElement("div");
    lema.className = "c-lema";
    lema.textContent = t.lema;
    hoja.appendChild(lema);

    var pie = document.createElement("div");
    pie.className = "c-pie";
    pie.textContent = t.contraPie;
    hoja.appendChild(pie);

    return hoja;
  }

  function construirLibro() {
    limpiarColaFotos();

    estado.grupos = agrupar(estado.menu, estado.categorias);

    var hojas = [hojaPortada(estado.grupos)];
    hojas = hojas.concat(construirHojasContenido(estado.grupos));
    hojas.push(hojaContra(estado.grupos));

    estado.hojas = hojas;
    estado.total = hojas.length;
    crearPaginasDom();
  }

  function crearPaginasDom() {
    paginasDom = [];
    estado.hojas.forEach(function (hoja, indice) {
      var numero = hoja.querySelector(".h-pie-num");
      if (numero) numero.textContent = String(indice + 1);

      var pagina = document.createElement("div");
      pagina.className = "page" + (indice === 0 ? " page--tapa" : "");
      pagina.appendChild(hoja);
      paginasDom.push(pagina);
    });
    estado.paginas = paginasDom;
    if (medidorEl) medidorEl.innerHTML = "";
  }

  /* ---------- montaje del libro ---------- */

  function ajustarEscalaHojas() {
    var primera = libroEl.querySelector(".page");
    if (!primera) return;
    var ancho = primera.offsetWidth;
    if (!ancho) return;
    var escalaHoja = ancho / ANCHO_HOJA;
    var hojas = libroEl.querySelectorAll(".hoja");
    for (var i = 0; i < hojas.length; i++) {
      hojas[i].style.setProperty("--s", escalaHoja);
    }
  }

  function iniciarObservador() {
    if (observador || typeof ResizeObserver !== "function") return;
    observador = new ResizeObserver(function () {
      ajustarEscalaHojas();
      if (!visor.hidden) ajustarVisor();
    });
    observador.observe(libroEl);
  }

  function montarLibro() {
    if (!paginasDom.length) return;

    if (pageFlip) {
      pageFlip.destroy();
      pageFlip = null;
    }

    if (!libroEl.isConnected && libroMarcoEl) {
      libroMarcoEl.appendChild(libroEl);
    }

    libroEl.className = "libro";
    libroEl.style.cssText = "";
    libroEl.innerHTML = "";

    var fragmento = document.createDocumentFragment();
    paginasDom.forEach(function (pagina) { fragmento.appendChild(pagina); });
    libroEl.appendChild(fragmento);

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
    procesarColaFotos();
    pageFlip.on("flip", function (evento) {
      pintarProgreso(evento.data);
      ajustarEscalaHojas();
      priorizarFotos(evento.data);
    });

    pintarProgreso(0);
    ajustarEscalaHojas();
    libroEl.classList.add("listo");
    btnZoom.disabled = false;
    if (overlay) overlay.classList.add("oculto");

    window.setTimeout(function () {
      ajustarEscalaHojas();
      priorizarFotos(0);
    }, 60);
    iniciarObservador();
  }

  function pintarProgreso(indice) {
    var total = estado.total || 1;
    var actual = Math.min(total, Math.max(1, indice + 1));
    paginaActualEl.textContent = String(actual);
    paginaTotalEl.textContent = String(total);
    barraEl.style.width = (actual / total) * 100 + "%";
    btnPrev.disabled = actual <= 1;
    btnNext.disabled = actual >= total;
  }

  function indiceActual() {
    try {
      if (pageFlip && typeof pageFlip.getCurrentPageIndex === "function") {
        return pageFlip.getCurrentPageIndex() || 0;
      }
    } catch (error) {
      /* sin libro montado */
    }
    return 0;
  }

  /* ---------- ampliar la página ---------- */

  function fijarVista() {
    visorHoja.style.transform =
      "translate3d(" + panX + "px," + panY + "px,0) scale(" + escala + ")";
    visorReset.textContent = Math.round(escala * 100) + "%";
    visorMenos.disabled = escala <= ESCALA_MIN + 0.001;
    visorMas.disabled = escala >= ESCALA_MAX - 0.001;
    visorAnterior.disabled = indiceVisor <= 0;
    visorSiguiente.disabled = indiceVisor >= estado.total - 1;
  }

  function limitarPan() {
    var caja = visorLienzo.getBoundingClientRect();
    var ancho = visorHoja.offsetWidth || 1;
    var alto = visorHoja.offsetHeight || 1;
    var maxX = Math.max(0, (ancho * escala - caja.width) / 2);
    var maxY = Math.max(0, (alto * escala - caja.height) / 2);
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

  function ajustarVisor() {
    if (visor.hidden) return;
    var caja = visorLienzo.getBoundingClientRect();
    var margen = 12;
    var ancho = Math.max(120, caja.width - margen * 2);
    var alto = Math.max(180, caja.height - margen * 2);
    var escalaHoja = Math.min(ancho / ANCHO_HOJA, alto / ALTO_HOJA);
    if (!isFinite(escalaHoja) || escalaHoja <= 0) escalaHoja = 0.2;

    visorHoja.style.width = Math.round(ANCHO_HOJA * escalaHoja) + "px";
    visorHoja.style.height = Math.round(ALTO_HOJA * escalaHoja) + "px";

    var hoja = visorHoja.querySelector(".hoja");
    if (hoja) hoja.style.setProperty("--s", escalaHoja);

    limitarPan();
    fijarVista();
  }

  function cargarPagina(indice) {
    if (!paginasDom.length) return;
    var t = TEXTOS[idioma];
    indiceVisor = Math.min(paginasDom.length - 1, Math.max(0, indice));

    visorHoja.innerHTML = "";
    var origen = paginasDom[indiceVisor];
    var hoja = origen ? origen.querySelector(".hoja") : null;
    if (hoja) {
      var clon = hoja.cloneNode(true);
      clon.style.setProperty("--s", 1);
      forzarFotosDe(clon);
      visorHoja.appendChild(clon);
    }

    visorHoja.setAttribute("aria-label", t.altPaginaAmpliada(indiceVisor + 1));
    visorTitulo.textContent =
      t.pagina + " " + (indiceVisor + 1) + " " + t.de + " " + paginasDom.length;

    escala = 1;
    panX = 0;
    panY = 0;
    ajustarVisor();
  }

  function abrirVisor() {
    if (!estado.total) return;
    visor.hidden = false;
    visor.setAttribute("aria-hidden", "false");
    document.body.classList.add("con-visor");
    cargarPagina(indiceActual());
    visorCerrar.focus();
  }

  function cerrarVisor() {
    if (visor.hidden) return;
    visor.hidden = true;
    visor.setAttribute("aria-hidden", "true");
    document.body.classList.remove("con-visor");
    visorHoja.innerHTML = "";
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
      pageFlip && pageFlip.turnToPage(estado.total - 1);
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

  /* ---------- cambio de idioma ---------- */

  async function cambiarIdioma(nuevo, guardar) {
    if (nuevo !== "es" && nuevo !== "en") return;
    if (nuevo === idioma && estado.total) return;

    var indice = indiceActual();
    var visorAbierto = !visor.hidden;
    var indiceEnVisor = indiceVisor;

    idioma = nuevo;
    if (guardar !== false) {
      try {
        window.localStorage.setItem(CLAVE_IDIOMA, idioma);
      } catch (error) {
        /* almacenamiento no disponible */
      }
    }
    marcarIdioma();
    aplicarTextos();

    if (!estado.menu.length) return;

    construirLibro();
    montarLibro();

    var destino = Math.min(indice, estado.total - 1);
    if (destino > 0 && pageFlip) {
      pageFlip.turnToPage(destino);
      pintarProgreso(destino);
    }

    if (visorAbierto) {
      cargarPagina(indiceEnVisor);
      visorTitulo.textContent =
        TEXTOS[idioma].pagina + " " + (indiceVisor + 1) + " " + TEXTOS[idioma].de + " " + estado.total;
    }
  }

  /* ---------- carga inicial ---------- */

  function mostrarError(motivo) {
    btnZoom.disabled = true;
    if (!overlay) return;
    var t = TEXTOS[idioma];
    overlay.classList.remove("oculto");
    overlay.innerHTML = "";

    var caja = document.createElement("div");
    caja.className = "cargando-error";

    var texto = document.createElement("p");
    texto.textContent = motivo === "vacio" ? t.menuVacio : t.errorCarga;
    caja.appendChild(texto);

    var boton = document.createElement("button");
    boton.type = "button";
    boton.className = "cargando-reintentar";
    boton.textContent = t.reintentar;
    boton.addEventListener("click", function () {
      boton.disabled = true;
      iniciar();
    });
    caja.appendChild(boton);

    overlay.appendChild(caja);
    overlayTexto = null;
  }

  async function iniciar() {
    idioma = idiomaInicial();
    marcarIdioma();
    aplicarTextos();

    try {
      var datos = await cargarMenu();
      estado.menu = datos.menu;
      estado.categorias = datos.categorias;
    } catch (error) {
      mostrarError("red");
      return;
    }

    if (!estado.menu.length) {
      mostrarError("vacio");
      return;
    }

    construirLibro();
    montarLibro();
  }

  iniciar();
})();
