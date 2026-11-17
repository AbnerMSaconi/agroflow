/* ==========================================================================
   SojaTech AgroFlow — /press (Esteira ao vivo para apresentação)
   Consome window.AgroAPI (api.js) e window.renderDetalhe / AgroDetalhe (detalhe.js).
   ========================================================================== */
(function () {
  "use strict";

  const COLUNAS = ["chegou", "processando", "aceito", "conferir", "rejeitado"];

  const RESUMO_PADRAO = {
    chegou: "Na fila de entrada",
    processando: "Processando…",
    aceito: "Processamento concluído",
    conferir: "Encaminhado para conferência",
    rejeitado: "Arquivo rejeitado",
  };

  const dom = {
    statusModelos: document.getElementById("status-modelos"),
    avisoModelos: document.getElementById("aviso-modelos"),
    btnExemplos: document.getElementById("btn-exemplos"),
    btnLimpar: document.getElementById("btn-limpar"),
    toast: document.getElementById("press-toast"),
    gaveta: document.getElementById("gaveta-detalhe"),
    gavetaBackdrop: document.getElementById("gaveta-backdrop"),
    gavetaConteudo: document.getElementById("gaveta-conteudo"),
    btnFecharGaveta: document.getElementById("btn-fechar-gaveta"),
    dropOverlay: document.getElementById("drop-overlay"),
    colunas: {},
  };

  for (const est of COLUNAS) {
    dom.colunas[est] = {
      contagem: document.getElementById(`cont-${est}`),
      lista: document.getElementById(`lista-${est}`),
    };
  }

  let ultimoEstado = null;
  let idSelecionado = null;
  let elementoFocoRetorno = null;
  let jaRenderizou = false;
  let limpandoEmCurso = false;
  let toastTimer = null;

  const estadosAnteriores = new Map(); // id -> estado
  const mapaCartoes = new Map(); // id -> HTMLElement

  const mqlReducedMotion =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

  function movimentoReduzido() {
    return Boolean(mqlReducedMotion && mqlReducedMotion.matches);
  }

  function mostrarToast(mensagem, tipo) {
    if (!dom.toast) {
      return;
    }
    if (toastTimer !== null) {
      clearTimeout(toastTimer);
      toastTimer = null;
    }
    dom.toast.textContent = mensagem;
    dom.toast.classList.toggle("toast-erro", tipo === "erro");
    dom.toast.hidden = false;
    toastTimer = setTimeout(() => {
      dom.toast.hidden = true;
      toastTimer = null;
    }, 3200);
  }

  function extrairExtensao(nomeArquivo) {
    if (!nomeArquivo || typeof nomeArquivo !== "string") {
      return "ARQ";
    }
    const base = nomeArquivo.split(/[/\\]/).pop() || "";
    const idx = base.lastIndexOf(".");
    if (idx <= 0 || idx === base.length - 1) {
      return "ARQ";
    }
    return base.slice(idx + 1, idx + 5).toUpperCase();
  }

  function criarSvgDocumento(labelText) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.9");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", "cartao-thumb-svg");

    const path = document.createElementNS(ns, "path");
    path.setAttribute(
      "d",
      "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
    );
    const poly = document.createElementNS(ns, "polyline");
    poly.setAttribute("points", "14 2 14 8 20 8");
    svg.appendChild(path);
    svg.appendChild(poly);

    const wrap = document.createElement("div");
    wrap.appendChild(svg);
    if (labelText) {
      const span = document.createElement("span");
      span.textContent = labelText;
      wrap.appendChild(span);
    }
    return wrap;
  }

  function criarSvgFolha() {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.9");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", "cartao-thumb-svg");

    const p1 = document.createElementNS(ns, "path");
    p1.setAttribute("d", "M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z");
    const p2 = document.createElementNS(ns, "path");
    p2.setAttribute("d", "M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12");
    svg.appendChild(p1);
    svg.appendChild(p2);
    return svg;
  }

  function preencherThumbFallback(thumb, item) {
    thumb.innerHTML = "";
    if (item.tipo === "nota") {
      const box = criarSvgDocumento("PDF");
      box.className = "cartao-thumb-doc cartao-thumb-pdf";
      thumb.appendChild(box);
      return;
    }
    if (item.tipo === "folha") {
      const box = document.createElement("div");
      box.className = "cartao-thumb-doc cartao-thumb-folha";
      box.appendChild(criarSvgFolha());
      thumb.appendChild(box);
      return;
    }
    const ext = extrairExtensao(item.arquivo);
    const box = criarSvgDocumento(ext);
    box.className = "cartao-thumb-doc cartao-thumb-ext";
    thumb.appendChild(box);
  }

  function atualizarThumb(thumb, item) {
    const ext = extrairExtensao(item.arquivo);
    const key = item.midia ? `midia:${item.midia}` : `tipo:${item.tipo}:${ext}`;
    if (thumb.dataset.thumbKey === key) {
      return;
    }
    thumb.dataset.thumbKey = key;

    if (item.midia) {
      thumb.innerHTML = "";
      const img = document.createElement("img");
      img.className = "cartao-thumb-img";
      img.src = item.midia;
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("error", () => {
        if (thumb.dataset.thumbKey === key) {
          preencherThumbFallback(thumb, item);
        }
      });
      thumb.appendChild(img);
    } else {
      preencherThumbFallback(thumb, item);
    }
  }

  function criarCartao(item) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cartao";
    btn.setAttribute("role", "listitem");
    btn.dataset.itemId = String(item.id);

    const thumb = document.createElement("div");
    thumb.className = "cartao-thumb";

    const corpo = document.createElement("div");
    corpo.className = "cartao-corpo";

    const nome = document.createElement("div");
    nome.className = "cartao-nome";

    const resumo = document.createElement("div");
    resumo.className = "cartao-resumo";

    const rodape = document.createElement("div");
    rodape.className = "cartao-rodape";

    const badgeSlot = document.createElement("span");
    badgeSlot.className = "cartao-badge-slot";

    const duracao = document.createElement("span");
    duracao.className = "cartao-duracao";

    rodape.appendChild(badgeSlot);
    rodape.appendChild(duracao);

    corpo.appendChild(nome);
    corpo.appendChild(resumo);
    corpo.appendChild(rodape);

    btn.appendChild(thumb);
    btn.appendChild(corpo);

    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.itemId);
      const atual = window.AgroAPI ? window.AgroAPI.obterItem(id) : null;
      if (atual) {
        abrirGaveta(atual, btn);
      }
    });

    return btn;
  }

  function atualizarCartao(btn, item) {
    const nomeTexto = item.arquivo || `Item #${item.id}`;
    const estado = COLUNAS.includes(item.estado) ? item.estado : "chegou";
    const resumoTexto = item.resumo || RESUMO_PADRAO[estado] || "";
    const duracaoTexto =
      item.duracao_ms !== null && item.duracao_ms !== undefined
        ? window.AgroDetalhe.formatarDuracao(item.duracao_ms)
        : "";

    const assinatura = JSON.stringify([
      nomeTexto,
      item.tipo,
      estado,
      resumoTexto,
      item.midia || "",
      duracaoTexto,
    ]);

    btn.classList.toggle("selecionado", Number(item.id) === Number(idSelecionado));

    if (btn.dataset.assinatura === assinatura) {
      return;
    }
    btn.dataset.assinatura = assinatura;

    const thumb = btn.querySelector(".cartao-thumb");
    const nome = btn.querySelector(".cartao-nome");
    const resumo = btn.querySelector(".cartao-resumo");
    const badgeSlot = btn.querySelector(".cartao-badge-slot");
    const duracao = btn.querySelector(".cartao-duracao");

    atualizarThumb(thumb, item);

    nome.textContent = nomeTexto;
    btn.title = nomeTexto;

    resumo.textContent = resumoTexto;

    badgeSlot.innerHTML = "";
    badgeSlot.appendChild(window.AgroDetalhe.criarBadgeSituacao(estado));

    if (duracaoTexto) {
      duracao.textContent = duracaoTexto;
      duracao.hidden = false;
    } else {
      duracao.textContent = "";
      duracao.hidden = true;
    }
  }

  function dispararAnimacaoClasse(el, classe, duracaoMs) {
    if (movimentoReduzido()) {
      return;
    }
    el.classList.remove("cartao-entrou", "cartao-mudou-coluna");
    void el.offsetWidth;
    el.classList.add(classe);
    window.setTimeout(() => {
      el.classList.remove(classe);
    }, duracaoMs);
  }

  function compararFilaAsc(a, b) {
    const recA = a.recebido_em || "";
    const recB = b.recebido_em || "";
    if (recA && recB && recA !== recB) {
      return recA < recB ? -1 : 1;
    }
    return Number(a.id) - Number(b.id);
  }

  function compararRecenteDesc(a, b) {
    return Number(b.id) - Number(a.id);
  }

  function renderEsteira(itens) {
    const porEstado = {
      chegou: [],
      processando: [],
      aceito: [],
      conferir: [],
      rejeitado: [],
    };

    const idsAtivos = new Set();

    for (const item of itens) {
      const est = COLUNAS.includes(item.estado) ? item.estado : "chegou";
      porEstado[est].push(item);
      idsAtivos.add(Number(item.id));
    }

    // Chegou e Processando em ordem de fila (menor recebido_em/id em cima).
    // Colunas finais com o mais recente em cima (maior id primeiro).
    porEstado.chegou.sort(compararFilaAsc);
    porEstado.processando.sort(compararFilaAsc);
    porEstado.aceito.sort(compararRecenteDesc);
    porEstado.conferir.sort(compararRecenteDesc);
    porEstado.rejeitado.sort(compararRecenteDesc);

    // Captura posições verticais antes da atualização para FLIP intra-coluna
    const rectsAntes = new Map();
    const reduzir = movimentoReduzido();
    if (jaRenderizou && !reduzir) {
      for (const [id, el] of mapaCartoes.entries()) {
        if (idsAtivos.has(id) && el.isConnected) {
          rectsAntes.set(id, {
            rect: el.getBoundingClientRect(),
            estado: estadosAnteriores.get(id),
          });
        }
      }
    }

    // Remove cartões que não existem mais (ex.: após /api/limpar)
    for (const [id, el] of mapaCartoes.entries()) {
      if (!idsAtivos.has(id)) {
        el.remove();
        mapaCartoes.delete(id);
        estadosAnteriores.delete(id);
      }
    }

    const cartoesNovos = [];
    const cartoesMudaramColuna = [];

    for (const est of COLUNAS) {
      const col = dom.colunas[est];
      const lista = porEstado[est];
      if (col.contagem) {
        col.contagem.textContent = String(lista.length);
      }
      if (!col.lista) {
        continue;
      }

      if (lista.length === 0) {
        col.lista.innerHTML = "";
        const vazio = document.createElement("div");
        vazio.className = "coluna-vazia";
        vazio.textContent = "Nenhum item";
        col.lista.appendChild(vazio);
        continue;
      }

      // Remove placeholder vazio se existir
      const placeholder = col.lista.querySelector(".coluna-vazia");
      if (placeholder) {
        placeholder.remove();
      }

      const fragmento = document.createDocumentFragment();
      for (const item of lista) {
        const id = Number(item.id);
        let el = mapaCartoes.get(id);
        const estadoAnterior = estadosAnteriores.get(id);

        if (!el) {
          el = criarCartao(item);
          mapaCartoes.set(id, el);
          if (jaRenderizou) {
            cartoesNovos.push(el);
          }
        } else if (jaRenderizou && estadoAnterior && estadoAnterior !== est) {
          cartoesMudaramColuna.push(el);
        }

        atualizarCartao(el, item);
        estadosAnteriores.set(id, est);
        fragmento.appendChild(el);
      }

      // Reordena sem recriar os nós existentes
      col.lista.innerHTML = "";
      col.lista.appendChild(fragmento);
    }

    if (jaRenderizou && !reduzir) {
      for (const el of cartoesNovos) {
        dispararAnimacaoClasse(el, "cartao-entrou", 320);
      }
      for (const el of cartoesMudaramColuna) {
        dispararAnimacaoClasse(el, "cartao-mudou-coluna", 380);
      }

      // FLIP vertical suave para cartões que se deslocaram dentro da mesma coluna
      for (const [id, info] of rectsAntes.entries()) {
        const el = mapaCartoes.get(id);
        if (!el || estadosAnteriores.get(id) !== info.estado) {
          continue;
        }
        const novoRect = el.getBoundingClientRect();
        const dy = info.rect.top - novoRect.top;
        if (Math.abs(dy) >= 2 && Math.abs(dy) < 600) {
          el.style.transition = "none";
          el.style.transform = `translate3d(0, ${dy}px, 0)`;
          void el.offsetWidth;
          el.style.transition = "transform 240ms cubic-bezier(0.22, 1, 0.36, 1)";
          el.style.transform = "translate3d(0, 0, 0)";
          window.setTimeout(() => {
            el.style.transition = "";
            el.style.transform = "";
          }, 260);
        }
      }
    }

    jaRenderizou = true;
  }

  function atualizarCabecalho(estado) {
    if (dom.statusModelos) {
      const pill = dom.statusModelos;
      const textoEl = pill.querySelector(".status-texto");
      pill.classList.remove("status-pronto", "status-carregando", "status-erro", "status-neutro");

      if (!estado.conectado && estado.inicializado) {
        pill.classList.add("status-erro");
        if (textoEl) {
          textoEl.textContent = "Sem conexão com o servidor";
        }
      } else if (estado.modelos === "prontos") {
        pill.classList.add("status-pronto");
        if (textoEl) {
          textoEl.textContent = "Modelos prontos";
        }
      } else if (estado.modelos === "faltando") {
        pill.classList.add("status-erro");
        if (textoEl) {
          textoEl.textContent = "Modelo de folhas ausente";
        }
      } else {
        pill.classList.add("status-carregando");
        if (textoEl) {
          textoEl.textContent = "Modelos carregando…";
        }
      }
    }

    if (dom.avisoModelos) {
      dom.avisoModelos.hidden = estado.modelos !== "faltando";
    }

    if (dom.btnLimpar) {
      const desabilitar = !estado.ocioso || limpandoEmCurso;
      dom.btnLimpar.disabled = desabilitar;
      dom.btnLimpar.title = estado.ocioso
        ? "Limpar itens e mídia da demonstração"
        : "Aguarde o processamento terminar para limpar";
    }
  }

  function atualizarGavetaSeAberta() {
    if (idSelecionado === null || !dom.gaveta || dom.gaveta.hidden) {
      return;
    }
    const item = window.AgroAPI ? window.AgroAPI.obterItem(idSelecionado) : null;
    if (!item) {
      fecharGaveta(false);
      return;
    }
    window.renderDetalhe(dom.gavetaConteudo, item);
  }

  function abrirGaveta(item, elementoOrigem) {
    if (!item || !dom.gaveta || !dom.gavetaConteudo) {
      return;
    }
    idSelecionado = Number(item.id);
    elementoFocoRetorno = elementoOrigem || document.activeElement;

    for (const [id, el] of mapaCartoes.entries()) {
      el.classList.toggle("selecionado", id === idSelecionado);
    }

    window.renderDetalhe(dom.gavetaConteudo, item);
    dom.gaveta.hidden = false;
    dom.gaveta.setAttribute("aria-hidden", "false");

    if (dom.btnFecharGaveta) {
      dom.btnFecharGaveta.focus();
    }
  }

  function fecharGaveta(restaurarFoco = true) {
    if (!dom.gaveta || dom.gaveta.hidden) {
      return;
    }
    dom.gaveta.hidden = true;
    dom.gaveta.setAttribute("aria-hidden", "true");
    idSelecionado = null;

    for (const el of mapaCartoes.values()) {
      el.classList.remove("selecionado");
    }

    if (
      restaurarFoco &&
      elementoFocoRetorno &&
      typeof elementoFocoRetorno.focus === "function" &&
      elementoFocoRetorno.isConnected
    ) {
      elementoFocoRetorno.focus();
    }
    elementoFocoRetorno = null;
  }

  async function aoClicarExemplos() {
    if (!window.AgroAPI || !dom.btnExemplos) {
      return;
    }
    dom.btnExemplos.disabled = true;
    try {
      await window.AgroAPI.enviarExemplos();
      mostrarToast("Amostra de demonstração enviada para a esteira.");
    } catch (err) {
      mostrarToast(err && err.message ? err.message : "Erro ao enviar exemplos.", "erro");
    } finally {
      dom.btnExemplos.disabled = false;
    }
  }

  async function aoClicarLimpar() {
    if (!window.AgroAPI || !dom.btnLimpar || dom.btnLimpar.disabled) {
      return;
    }
    limpandoEmCurso = true;
    dom.btnLimpar.disabled = true;
    try {
      await window.AgroAPI.limpar();
      fecharGaveta(false);
      mostrarToast("Esteira limpa.");
    } catch (err) {
      mostrarToast(err && err.message ? err.message : "Não foi possível limpar.", "erro");
    } finally {
      limpandoEmCurso = false;
      if (ultimoEstado) {
        atualizarCabecalho(ultimoEstado);
      }
    }
  }

  async function aoSoltarArquivos(fileList) {
    if (!window.AgroAPI) {
      return;
    }
    const qtd = fileList ? fileList.length : 0;
    if (qtd === 0) {
      return;
    }
    try {
      const resp = await window.AgroAPI.enviarArquivos(fileList);
      const recebidos = resp && typeof resp.recebidos === "number" ? resp.recebidos : qtd;
      mostrarToast(
        recebidos === 1
          ? "1 arquivo enviado para a esteira."
          : `${recebidos} arquivos enviados para a esteira.`
      );
    } catch (err) {
      mostrarToast(err && err.message ? err.message : "Falha no envio dos arquivos.", "erro");
    }
  }

  function aoMudarEstado(estado) {
    ultimoEstado = estado;
    atualizarCabecalho(estado);
    renderEsteira(Array.isArray(estado.itens) ? estado.itens : []);
    atualizarGavetaSeAberta();
  }

  function iniciarPagina() {
    if (!window.AgroAPI || typeof window.renderDetalhe !== "function") {
      console.error("[press] AgroAPI ou renderDetalhe não carregados.");
      return;
    }

    if (dom.btnExemplos) {
      dom.btnExemplos.addEventListener("click", aoClicarExemplos);
    }
    if (dom.btnLimpar) {
      dom.btnLimpar.addEventListener("click", aoClicarLimpar);
    }
    if (dom.btnFecharGaveta) {
      dom.btnFecharGaveta.addEventListener("click", () => fecharGaveta(true));
    }
    if (dom.gavetaBackdrop) {
      dom.gavetaBackdrop.addEventListener("click", () => fecharGaveta(true));
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && dom.gaveta && !dom.gaveta.hidden) {
        e.preventDefault();
        fecharGaveta(true);
      }
    });

    const destruirDrop = window.AgroAPI.configurarDrop(document, aoSoltarArquivos, {
      classeAtivo: "arrastando-ativo",
      onDragStateChange: (ativo) => {
        if (dom.dropOverlay) {
          dom.dropOverlay.setAttribute("aria-hidden", ativo ? "false" : "true");
        }
      },
    });

    const cancelarAssinatura = window.AgroAPI.assinar(aoMudarEstado);
    window.AgroAPI.iniciar(500);

    window.addEventListener("beforeunload", () => {
      cancelarAssinatura();
      destruirDrop();
      window.AgroAPI.parar();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarPagina);
  } else {
    iniciarPagina();
  }
})();
