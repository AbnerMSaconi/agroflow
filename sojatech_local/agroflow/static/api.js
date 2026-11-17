/* ==========================================================================
   SojaTech AgroFlow — Cliente da API (/api/estado, upload, exemplos, limpar)
   Compartilhado entre /prod e /press via window.AgroAPI.
   ========================================================================== */
(function (global) {
  "use strict";

  const LIMITE_ITENS = 200;
  const INTERVALO_PADRAO_MS = 500;

  const estado = {
    versao: null,
    modelos: "carregando",
    limiares: { nota: 0.05, folha: 0.9 },
    ocioso: true,
    itens: [],
    conectado: false,
    erro: null,
    inicializado: false,
  };

  const mapaItens = new Map();
  const ouvintes = new Set();

  let timerId = null;
  let ativo = false;
  let intervaloMs = INTERVALO_PADRAO_MS;
  let requisicaoEmCurso = null;
  let atualizarPendente = false;

  function clonarEstado() {
    return {
      versao: estado.versao,
      modelos: estado.modelos,
      limiares: { ...estado.limiares },
      ocioso: estado.ocioso,
      itens: estado.itens.slice(),
      conectado: estado.conectado,
      erro: estado.erro,
      inicializado: estado.inicializado,
    };
  }

  function notificar(info) {
    const snapshot = clonarEstado();
    ouvintes.forEach((fn) => {
      try {
        fn(snapshot, info || {});
      } catch (err) {
        console.error("[AgroAPI] Erro em ouvinte:", err);
      }
    });
  }

  function reconstruirListaItens() {
    const lista = Array.from(mapaItens.values());
    lista.sort((a, b) => Number(b.id) - Number(a.id));
    if (lista.length > LIMITE_ITENS) {
      lista.length = LIMITE_ITENS;
      mapaItens.clear();
      for (const item of lista) {
        mapaItens.set(Number(item.id), item);
      }
    }
    estado.itens = lista;
  }

  function aplicarRespostaEstado(payload) {
    const mudouAlgo =
      !estado.inicializado ||
      payload.completo ||
      (Array.isArray(payload.itens) && payload.itens.length > 0) ||
      estado.modelos !== payload.modelos ||
      estado.ocioso !== payload.ocioso ||
      estado.versao !== payload.versao ||
      !estado.conectado;

    estado.versao = payload.versao;
    if (payload.modelos) {
      estado.modelos = payload.modelos;
    }
    if (payload.limiares) {
      estado.limiares = { ...estado.limiares, ...payload.limiares };
    }
    if (typeof payload.ocioso === "boolean") {
      estado.ocioso = payload.ocioso;
    }

    if (payload.completo) {
      mapaItens.clear();
      if (Array.isArray(payload.itens)) {
        for (const item of payload.itens) {
          mapaItens.set(Number(item.id), item);
        }
      }
      reconstruirListaItens();
    } else if (Array.isArray(payload.itens) && payload.itens.length > 0) {
      for (const item of payload.itens) {
        mapaItens.set(Number(item.id), item);
      }
      reconstruirListaItens();
    }

    estado.conectado = true;
    estado.erro = null;
    estado.inicializado = true;

    if (mudouAlgo) {
      notificar({ completo: Boolean(payload.completo) });
    }
  }

  async function buscarEstado() {
    if (requisicaoEmCurso) {
      atualizarPendente = true;
      return requisicaoEmCurso;
    }

    const url =
      estado.versao !== null && estado.versao !== undefined
        ? `/api/estado?desde=${encodeURIComponent(estado.versao)}`
        : "/api/estado";

    requisicaoEmCurso = (async () => {
      try {
        const resp = await fetch(url, {
          method: "GET",
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const dados = await resp.json();
        aplicarRespostaEstado(dados);
      } catch (err) {
        const eraConectado = estado.conectado;
        estado.conectado = false;
        estado.erro = err && err.message ? err.message : "Falha na conexão";
        if (eraConectado || !estado.inicializado) {
          notificar({ erro: estado.erro });
        }
      } finally {
        requisicaoEmCurso = null;
        if (atualizarPendente) {
          atualizarPendente = false;
          buscarEstado();
        } else if (ativo) {
          agendarProximo();
        }
      }
    })();

    return requisicaoEmCurso;
  }

  function agendarProximo() {
    if (timerId !== null) {
      clearTimeout(timerId);
    }
    if (!ativo) {
      return;
    }
    timerId = setTimeout(() => {
      timerId = null;
      if (ativo) {
        buscarEstado();
      }
    }, intervaloMs);
  }

  function iniciar(ms) {
    if (typeof ms === "number" && ms >= 100) {
      intervaloMs = ms;
    }
    if (ativo) {
      return;
    }
    ativo = true;
    buscarEstado();
  }

  function parar() {
    ativo = false;
    if (timerId !== null) {
      clearTimeout(timerId);
      timerId = null;
    }
  }

  function atualizar() {
    if (timerId !== null) {
      clearTimeout(timerId);
      timerId = null;
    }
    return buscarEstado();
  }

  function assinar(callback) {
    if (typeof callback !== "function") {
      return function () {};
    }
    ouvintes.add(callback);
    if (estado.inicializado) {
      try {
        callback(clonarEstado(), { inicial: true });
      } catch (err) {
        console.error("[AgroAPI] Erro em ouvinte inicial:", err);
      }
    }
    return function cancelar() {
      ouvintes.delete(callback);
    };
  }

  function obterEstado() {
    return clonarEstado();
  }

  function obterItem(id) {
    if (id === null || id === undefined) {
      return null;
    }
    return mapaItens.get(Number(id)) || null;
  }

  async function lerErroHttp(resp) {
    let mensagem = `Erro HTTP ${resp.status}`;
    try {
      const texto = await resp.text();
      if (texto) {
        try {
          const json = JSON.parse(texto);
          if (json && typeof json.detail === "string") {
            mensagem = json.detail;
          } else if (json && typeof json.erro === "string") {
            mensagem = json.erro;
          } else {
            mensagem = texto;
          }
        } catch (_) {
          mensagem = texto;
        }
      }
    } catch (_) {
      // ignora erro ao ler corpo
    }
    const erro = new Error(mensagem);
    erro.status = resp.status;
    return erro;
  }

  async function enviarArquivos(fileList) {
    const arquivos = Array.from(fileList || []);
    if (arquivos.length === 0) {
      return { recebidos: 0 };
    }
    const form = new FormData();
    for (const arquivo of arquivos) {
      form.append("arquivos", arquivo);
    }
    const resp = await fetch("/api/enviar", {
      method: "POST",
      body: form,
    });
    if (!resp.ok) {
      throw await lerErroHttp(resp);
    }
    const dados = await resp.json();
    atualizar();
    return dados;
  }

  async function enviarExemplos() {
    const resp = await fetch("/api/exemplos", {
      method: "POST",
    });
    if (!resp.ok) {
      throw await lerErroHttp(resp);
    }
    const dados = await resp.json();
    atualizar();
    return dados;
  }

  async function limpar() {
    const resp = await fetch("/api/limpar", {
      method: "POST",
    });
    if (!resp.ok) {
      throw await lerErroHttp(resp);
    }
    const dados = await resp.json();
    await atualizar();
    return dados;
  }

  function contemArquivos(evento) {
    const dt = evento && evento.dataTransfer;
    if (!dt || !dt.types) {
      return false;
    }
    const tipos = Array.from(dt.types);
    return tipos.includes("Files");
  }

  function configurarDrop(elemento, onArquivos, opcoes) {
    if (!elemento || typeof onArquivos !== "function") {
      return function () {};
    }
    const opts = opcoes || {};
    const classeAtivo = opts.classeAtivo || "arrastando-ativo";
    const alvoClasse =
      opts.alvoClasse ||
      (elemento === global || elemento === document
        ? document.documentElement
        : elemento);

    let profundidade = 0;

    function definirAtivo(ligado) {
      if (alvoClasse && alvoClasse.classList) {
        alvoClasse.classList.toggle(classeAtivo, ligado);
      }
      if (typeof opts.onDragStateChange === "function") {
        opts.onDragStateChange(ligado);
      }
    }

    function aoDragEnter(e) {
      if (!contemArquivos(e)) {
        return;
      }
      e.preventDefault();
      profundidade += 1;
      if (profundidade === 1) {
        definirAtivo(true);
      }
    }

    function aoDragOver(e) {
      if (!contemArquivos(e)) {
        return;
      }
      e.preventDefault();
      if (e.dataTransfer) {
        e.dataTransfer.dropEffect = "copy";
      }
    }

    function aoDragLeave(e) {
      if (profundidade === 0) {
        return;
      }
      e.preventDefault();
      profundidade = Math.max(0, profundidade - 1);
      if (profundidade === 0) {
        definirAtivo(false);
      }
    }

    function aoDrop(e) {
      if (!contemArquivos(e)) {
        profundidade = 0;
        definirAtivo(false);
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      profundidade = 0;
      definirAtivo(false);
      const files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length > 0) {
        onArquivos(files);
      }
    }

    function resetar() {
      if (profundidade !== 0) {
        profundidade = 0;
        definirAtivo(false);
      }
    }

    elemento.addEventListener("dragenter", aoDragEnter);
    elemento.addEventListener("dragover", aoDragOver);
    elemento.addEventListener("dragleave", aoDragLeave);
    elemento.addEventListener("drop", aoDrop);
    global.addEventListener("blur", resetar);
    global.addEventListener("dragend", resetar);

    return function destruir() {
      elemento.removeEventListener("dragenter", aoDragEnter);
      elemento.removeEventListener("dragover", aoDragOver);
      elemento.removeEventListener("dragleave", aoDragLeave);
      elemento.removeEventListener("drop", aoDrop);
      global.removeEventListener("blur", resetar);
      global.removeEventListener("dragend", resetar);
      resetar();
    };
  }

  global.AgroAPI = {
    iniciar,
    parar,
    atualizar,
    assinar,
    obterEstado,
    obterItem,
    enviarArquivos,
    enviarExemplos,
    limpar,
    configurarDrop,
    // Aliases em inglês para conveniência
    startPolling: iniciar,
    stopPolling: parar,
    refresh: atualizar,
    subscribe: assinar,
    getState: obterEstado,
    getItem: obterItem,
  };
})(window);
