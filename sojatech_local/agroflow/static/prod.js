/* ==========================================================================
   SojaTech AgroFlow — Lógica da página /prod (Operação / Caixa de entrada)
   ========================================================================== */
(function (global) {
  "use strict";

  const { AgroAPI, AgroDetalhe, renderDetalhe } = global;

  const statusObservador = document.getElementById("status-observador");
  const statusModelos = document.getElementById("status-modelos");
  const avisoModelos = document.getElementById("aviso-modelos");
  const btnExemplos = document.getElementById("btn-exemplos");
  const btnLimpar = document.getElementById("btn-limpar");
  const zonaSoltar = document.getElementById("zona-soltar");
  const inputArquivos = document.getElementById("input-arquivos");
  const btnSelecionar = document.getElementById("btn-selecionar");
  const feedbackAcao = document.getElementById("feedback-acao");
  const listaItens = document.getElementById("lista-itens");
  const painelDetalhe = document.getElementById("painel-detalhe");
  const botoesFiltro = Array.from(document.querySelectorAll(".filtro-btn"));

  const contadores = {
    todos: document.getElementById("cont-todos"),
    aceito: document.getElementById("cont-aceito"),
    conferir: document.getElementById("cont-conferir"),
    rejeitado: document.getElementById("cont-rejeitado"),
    andamento: document.getElementById("cont-andamento"),
  };

  let filtroAtual = "todos";
  let idSelecionado = null;
  let ultimoEstado = AgroAPI.obterEstado();
  let itensFiltradosAtuais = [];
  let ultimaAssinaturaLista = "";
  let timerFeedback = null;

  const SIGLA_TIPO = {
    nota: "PDF",
    folha: "IMG",
    outro: "ARQ",
  };

  function mostrarFeedback(mensagem, tipo) {
    if (timerFeedback !== null) {
      clearTimeout(timerFeedback);
      timerFeedback = null;
    }
    feedbackAcao.textContent = mensagem;
    feedbackAcao.className = `feedback-acao${
      tipo === "erro" ? " feedback-erro" : tipo === "ok" ? " feedback-ok" : ""
    }`;
    feedbackAcao.hidden = false;
    timerFeedback = setTimeout(() => {
      feedbackAcao.hidden = true;
      timerFeedback = null;
    }, 4500);
  }

  function atualizarStatus(estado) {
    // Observador / conexão
    const obsTexto = statusObservador.querySelector(".status-texto");
    if (!estado.inicializado) {
      statusObservador.className = "status-pill status-carregando";
      obsTexto.textContent = "Conectando observador…";
    } else if (estado.conectado) {
      statusObservador.className = "status-pill status-ok";
      obsTexto.textContent = estado.ocioso
        ? "Observador ativo · ocioso"
        : "Observador ativo · processando";
    } else {
      statusObservador.className = "status-pill status-erro";
      obsTexto.textContent = "Sem conexão com o servidor";
    }

    // Modelos
    const modTexto = statusModelos.querySelector(".status-texto");
    if (estado.modelos === "prontos") {
      statusModelos.className = "status-pill status-ok";
      modTexto.textContent = "Modelos prontos";
      avisoModelos.hidden = true;
    } else if (estado.modelos === "faltando") {
      statusModelos.className = "status-pill status-alerta";
      modTexto.textContent = "Modelo de folhas faltando";
      avisoModelos.hidden = false;
    } else {
      statusModelos.className = "status-pill status-carregando";
      modTexto.textContent = "Carregando modelos…";
      avisoModelos.hidden = true;
    }

    // Limpar fica desabilitado quando !ocioso
    btnLimpar.disabled = !estado.ocioso;
    btnLimpar.title = estado.ocioso
      ? "Limpar itens da tela e mídia temporária"
      : "Aguarde o fim do processamento para limpar";
  }

  function pertenceAoFiltro(item, filtro) {
    if (filtro === "todos") {
      return true;
    }
    if (filtro === "andamento") {
      return item.estado === "chegou" || item.estado === "processando";
    }
    return item.estado === filtro;
  }

  function atualizarContadores(itens) {
    const counts = {
      todos: itens.length,
      aceito: 0,
      conferir: 0,
      rejeitado: 0,
      andamento: 0,
    };
    for (const item of itens) {
      if (item.estado === "aceito") counts.aceito += 1;
      else if (item.estado === "conferir") counts.conferir += 1;
      else if (item.estado === "rejeitado") counts.rejeitado += 1;
      else counts.andamento += 1;
    }
    for (const chave of Object.keys(contadores)) {
      if (contadores[chave]) {
        contadores[chave].textContent = String(counts[chave]);
      }
    }
  }

  function criarLinhaItem(item) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `item-linha${Number(item.id) === Number(idSelecionado) ? " selecionado" : ""}`;
    btn.dataset.itemId = String(item.id);
    btn.setAttribute("role", "option");
    btn.setAttribute(
      "aria-selected",
      Number(item.id) === Number(idSelecionado) ? "true" : "false"
    );

    const topo = document.createElement("div");
    topo.className = "item-linha-topo";

    const nomeGrupo = document.createElement("div");
    nomeGrupo.className = "item-nome-grupo";

    const sigla = document.createElement("span");
    sigla.className = "item-tipo-sigla";
    sigla.textContent = SIGLA_TIPO[item.tipo] || "ARQ";

    const nome = document.createElement("span");
    nome.className = "item-nome";
    nome.textContent = item.arquivo || `Item #${item.id}`;
    nome.title = item.arquivo || "";

    nomeGrupo.appendChild(sigla);
    nomeGrupo.appendChild(nome);

    topo.appendChild(nomeGrupo);
    topo.appendChild(AgroDetalhe.criarBadgeSituacao(item.estado));

    const rodape = document.createElement("div");
    rodape.className = "item-linha-rodape";

    const resumo = document.createElement("span");
    resumo.className = "item-resumo";
    resumo.textContent = item.resumo || "—";

    const duracao = document.createElement("span");
    duracao.className = "item-duracao";
    duracao.textContent = AgroDetalhe.formatarDuracao(item.duracao_ms);

    rodape.appendChild(resumo);
    rodape.appendChild(duracao);

    btn.appendChild(topo);
    btn.appendChild(rodape);

    btn.addEventListener("click", () => {
      selecionarItem(item.id, false);
    });

    return btn;
  }

  function renderLista(estado) {
    const itens = Array.isArray(estado.itens) ? estado.itens : [];
    atualizarContadores(itens);

    itensFiltradosAtuais = itens.filter((item) => pertenceAoFiltro(item, filtroAtual));

    const assinatura = JSON.stringify({
      filtro: filtroAtual,
      selecionado: idSelecionado,
      itens: itensFiltradosAtuais.map((i) => [
        i.id,
        i.estado,
        i.resumo,
        i.duracao_ms,
        i.arquivo,
      ]),
    });

    if (assinatura === ultimaAssinaturaLista) {
      return;
    }
    ultimaAssinaturaLista = assinatura;

    const focoEstavaNaLista =
      document.activeElement && listaItens.contains(document.activeElement);

    listaItens.innerHTML = "";
    if (itensFiltradosAtuais.length === 0) {
      const vazio = document.createElement("div");
      vazio.className = "lista-vazia";
      vazio.textContent =
        itens.length === 0
          ? "Nenhum arquivo na caixa de entrada ainda. Solte PDFs/imagens acima ou clique em \"Enviar exemplos\"."
          : "Nenhum item corresponde ao filtro selecionado.";
      listaItens.appendChild(vazio);
      return;
    }

    const fragmento = document.createDocumentFragment();
    for (const item of itensFiltradosAtuais) {
      fragmento.appendChild(criarLinhaItem(item));
    }
    listaItens.appendChild(fragmento);

    if (focoEstavaNaLista && idSelecionado !== null) {
      const ativo = listaItens.querySelector(
        `.item-linha[data-item-id="${CSS.escape(String(idSelecionado))}"]`
      );
      if (ativo) {
        ativo.focus({ preventScroll: true });
      }
    }
  }

  function renderPainelDetalhe() {
    const item =
      idSelecionado !== null ? AgroAPI.obterItem(idSelecionado) : null;
    if (idSelecionado !== null && !item) {
      idSelecionado = null;
    }
    renderDetalhe(painelDetalhe, item);
  }

  function selecionarItem(id, rolarAte) {
    idSelecionado = id;
    renderLista(ultimoEstado);
    renderPainelDetalhe();

    if (rolarAte && id !== null) {
      const linha = listaItens.querySelector(
        `.item-linha[data-item-id="${CSS.escape(String(id))}"]`
      );
      if (linha) {
        linha.scrollIntoView({ block: "nearest" });
      }
    }
  }

  function aoAtualizarEstado(estado) {
    ultimoEstado = estado;
    atualizarStatus(estado);

    if (idSelecionado !== null && !AgroAPI.obterItem(idSelecionado)) {
      idSelecionado = null;
    }

    renderLista(estado);
    renderPainelDetalhe();
  }

  // Filtros
  for (const btn of botoesFiltro) {
    btn.addEventListener("click", () => {
      const novoFiltro = btn.dataset.filtro || "todos";
      if (novoFiltro === filtroAtual) {
        return;
      }
      filtroAtual = novoFiltro;
      for (const b of botoesFiltro) {
        const ativo = b === btn;
        b.classList.toggle("ativo", ativo);
        b.setAttribute("aria-selected", ativo ? "true" : "false");
      }
      renderLista(ultimoEstado);
    });
  }

  // Navegação por teclado (ArrowUp e ArrowDown)
  document.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") {
      return;
    }
    if (e.altKey || e.ctrlKey || e.metaKey) {
      return;
    }
    const alvo = e.target;
    if (
      alvo &&
      (alvo.tagName === "INPUT" ||
        alvo.tagName === "TEXTAREA" ||
        alvo.tagName === "SELECT" ||
        alvo.isContentEditable)
    ) {
      return;
    }
    if (itensFiltradosAtuais.length === 0) {
      return;
    }

    e.preventDefault();
    const idxAtual = itensFiltradosAtuais.findIndex(
      (item) => Number(item.id) === Number(idSelecionado)
    );

    let proximoIdx = 0;
    if (idxAtual === -1) {
      proximoIdx = 0;
    } else if (e.key === "ArrowDown") {
      proximoIdx = Math.min(itensFiltradosAtuais.length - 1, idxAtual + 1);
    } else {
      proximoIdx = Math.max(0, idxAtual - 1);
    }

    selecionarItem(itensFiltradosAtuais[proximoIdx].id, true);
  });

  // Upload de arquivos (clique + drag-and-drop)
  async function processarEnvioArquivos(fileList) {
    const qtd = fileList ? fileList.length : 0;
    if (qtd === 0) {
      return;
    }
    try {
      const resp = await AgroAPI.enviarArquivos(fileList);
      const n = resp && typeof resp.recebidos === "number" ? resp.recebidos : qtd;
      mostrarFeedback(
        n === 1
          ? "1 arquivo enviado para a fila de entrada."
          : `${n} arquivos enviados para a fila de entrada.`,
        "ok"
      );
    } catch (err) {
      mostrarFeedback(
        `Erro ao enviar arquivos: ${err && err.message ? err.message : "falha desconhecida"}`,
        "erro"
      );
    }
  }

  btnSelecionar.addEventListener("click", (e) => {
    e.stopPropagation();
    inputArquivos.click();
  });

  zonaSoltar.addEventListener("click", () => {
    inputArquivos.click();
  });

  zonaSoltar.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      inputArquivos.click();
    }
  });

  inputArquivos.addEventListener("change", () => {
    if (inputArquivos.files && inputArquivos.files.length > 0) {
      processarEnvioArquivos(inputArquivos.files);
      inputArquivos.value = "";
    }
  });

  AgroAPI.configurarDrop(document.body, processarEnvioArquivos, {
    alvoClasse: zonaSoltar,
    classeAtivo: "arrastando-ativo",
  });

  // Botões de ação: Enviar exemplos e Limpar
  btnExemplos.addEventListener("click", async () => {
    btnExemplos.disabled = true;
    try {
      await AgroAPI.enviarExemplos();
      mostrarFeedback("Amostra de exemplos iniciada em segundo plano.", "ok");
    } catch (err) {
      mostrarFeedback(
        `Erro ao enviar exemplos: ${err && err.message ? err.message : "falha"}`,
        "erro"
      );
    } finally {
      btnExemplos.disabled = false;
    }
  });

  btnLimpar.addEventListener("click", async () => {
    if (btnLimpar.disabled) {
      return;
    }
    btnLimpar.disabled = true;
    try {
      await AgroAPI.limpar();
      idSelecionado = null;
      renderPainelDetalhe();
      mostrarFeedback("Histórico do fluxo e mídia limpos.", "ok");
    } catch (err) {
      mostrarFeedback(
        err && err.status === 409
          ? "Aguarde os itens em andamento terminarem antes de limpar."
          : `Erro ao limpar: ${err && err.message ? err.message : "falha"}`,
        "erro"
      );
    } finally {
      btnLimpar.disabled = !ultimoEstado.ocioso;
    }
  });

  // Inicializa estado vazio do detalhe e polling
  renderPainelDetalhe();
  AgroAPI.assinar(aoAtualizarEstado);
  AgroAPI.iniciar(500);
})(window);
