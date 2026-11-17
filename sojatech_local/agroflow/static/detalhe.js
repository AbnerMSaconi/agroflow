/* ==========================================================================
   SojaTech AgroFlow — Componente compartilhado de detalhe do item
   Usado por /prod e /press via window.renderDetalhe(container, item).
   ========================================================================== */
(function (global) {
  "use strict";

  const MAPA_SITUACAO = {
    aceito: { icone: "✓", texto: "aceito", classe: "badge-aceito" },
    conferir: { icone: "!", texto: "conferir", classe: "badge-conferir" },
    rejeitado: { icone: "✕", texto: "rejeitado", classe: "badge-rejeitado" },
    processando: { icone: "⟳", texto: "processando", classe: "badge-processando" },
    chegou: { icone: "•", texto: "chegou", classe: "badge-chegou" },
  };

  const MAPA_TIPO = {
    nota: "Nota fiscal (DANFE)",
    folha: "Foto de folha",
    outro: "Outro arquivo",
  };

  const ROTULOS_CAMPO_PADRAO = {
    cnpj_emitente: "CNPJ do emitente",
    numero: "Número da NF-e",
    data_emissao: "Data de emissão",
    valor_total: "Valor total",
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function situacaoInfo(estado) {
    return MAPA_SITUACAO[estado] || MAPA_SITUACAO.chegou;
  }

  function criarBadgeSituacao(estado) {
    const info = situacaoInfo(estado);
    const badge = el("span", `badge-situacao ${info.classe}`);
    badge.appendChild(el("span", "badge-icone", info.icone));
    badge.appendChild(el("span", "badge-texto", info.texto));
    return badge;
  }

  function formatarDuracao(ms) {
    if (ms === null || ms === undefined || Number.isNaN(Number(ms))) {
      return "—";
    }
    const valor = Number(ms);
    if (valor < 1000) {
      return `${Math.round(valor)} ms`;
    }
    return `${(valor / 1000).toFixed(2).replace(".", ",")} s`;
  }

  function formatarPorcentagem(valor, casas = 1) {
    const num = Math.max(0, Math.min(1, Number(valor) || 0)) * 100;
    return `${num.toFixed(casas).replace(".", ",")}%`;
  }

  function formatarHorario(iso) {
    if (!iso) {
      return "";
    }
    try {
      const dt = new Date(iso);
      if (Number.isNaN(dt.getTime())) {
        return String(iso);
      }
      return dt.toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (_) {
      return String(iso);
    }
  }

  function renderEstadoVazio(container) {
    const vazio = el("div", "detalhe-vazio");
    vazio.appendChild(el("h3", "detalhe-vazio-titulo", "Nenhum item selecionado"));
    vazio.appendChild(
      el(
        "p",
        "detalhe-vazio-texto",
        "Selecione um arquivo na lista para inspecionar a extração da nota fiscal ou o diagnóstico da folha."
      )
    );
    container.appendChild(vazio);
  }

  function renderCabecalho(item) {
    const cabecalho = el("header", "detalhe-cabecalho");
    const grupo = el("div", "detalhe-titulo-grupo");

    grupo.appendChild(el("span", "detalhe-tipo-tag", MAPA_TIPO[item.tipo] || "Arquivo"));
    grupo.appendChild(el("h2", "detalhe-arquivo", item.arquivo || `Item #${item.id}`));

    const meta = el("div", "detalhe-meta-linha");
    if (item.recebido_em) {
      meta.appendChild(el("span", null, `Recebido às ${formatarHorario(item.recebido_em)}`));
    }
    if (item.duracao_ms !== null && item.duracao_ms !== undefined) {
      meta.appendChild(el("span", null, `Duração: ${formatarDuracao(item.duracao_ms)}`));
    }
    grupo.appendChild(meta);

    cabecalho.appendChild(grupo);
    cabecalho.appendChild(criarBadgeSituacao(item.estado));
    return cabecalho;
  }

  function renderNota(root, item) {
    const nota = item.nota || {};
    const campos = Array.isArray(nota.campos) ? nota.campos : [];

    const layout = el("div", "detalhe-nota-layout");
    const mapaCaixas = new Map();

    // Lado esquerdo: imagem da DANFE com caixas sobrepostas
    const quadro = el("div", "danfe-quadro");
    if (item.midia) {
      const palco = el("div", "danfe-palco");
      const img = el("img", "danfe-img");
      img.src = item.midia;
      img.alt = `DANFE de ${item.arquivo || "nota fiscal"}`;
      img.loading = "lazy";
      palco.appendChild(img);

      for (const campo of campos) {
        if (!campo || !campo.caixa) {
          continue;
        }
        const c = campo.caixa;
        const sit = campo.situacao === "baixa" ? "baixa" : "ok";
        const box = el("div", `danfe-caixa danfe-caixa-${sit}`);
        box.style.left = `${Number(c.x)}%`;
        box.style.top = `${Number(c.y)}%`;
        box.style.width = `${Number(c.w)}%`;
        box.style.height = `${Number(c.h)}%`;

        const rotulo = campo.rotulo || ROTULOS_CAMPO_PADRAO[campo.campo] || campo.campo;
        const confTexto = formatarPorcentagem(campo.confianca, 0);
        box.title = `${rotulo}: ${campo.exibicao || campo.valor || ""} (${confTexto})`;

        const etiqueta = el("span", "danfe-caixa-etiqueta", `${rotulo} (${confTexto})`);
        box.appendChild(etiqueta);

        palco.appendChild(box);
        mapaCaixas.set(campo.campo, box);
      }

      quadro.appendChild(palco);
    } else {
      quadro.appendChild(el("p", "detalhe-vazio-texto", "Pré-visualização da DANFE indisponível."));
    }
    layout.appendChild(quadro);

    // Lado direito: lista dos 4 campos extraídos
    const lista = el("div", "campos-lista");
    for (const campo of campos) {
      const sit = campo.situacao || "ok";
      const card = el(
        "div",
        `campo-card${sit === "baixa" ? " campo-baixa" : ""}${
          sit === "nao_encontrado" ? " campo-nao-encontrado" : ""
        }`
      );

      const topo = el("div", "campo-topo");
      const rotulo = campo.rotulo || ROTULOS_CAMPO_PADRAO[campo.campo] || campo.campo;
      topo.appendChild(el("span", "campo-rotulo", rotulo));

      const sitTexto =
        sit === "ok"
          ? "ok"
          : sit === "baixa"
          ? "confiança baixa"
          : "não encontrado";
      const sitClasse =
        sit === "ok"
          ? "campo-situacao-ok"
          : sit === "baixa"
          ? "campo-situacao-baixa"
          : "campo-situacao-nao-encontrado";
      topo.appendChild(el("span", `campo-situacao-tag ${sitClasse}`, sitTexto));
      card.appendChild(topo);

      const valorTexto =
        sit === "nao_encontrado"
          ? "Campo não encontrado"
          : campo.exibicao || campo.valor || "—";
      card.appendChild(el("div", "campo-valor", valorTexto));

      const confLinha = el("div", "campo-conf-linha");
      const trilho = el("div", "conf-barra-trilho");
      const preench = el("div", "conf-barra-preenchimento");
      const pctNum = Math.max(0, Math.min(100, (Number(campo.confianca) || 0) * 100));
      preench.style.width = `${pctNum}%`;
      trilho.appendChild(preench);
      confLinha.appendChild(trilho);
      confLinha.appendChild(el("span", "campo-conf-pct", formatarPorcentagem(campo.confianca, 0)));
      card.appendChild(confLinha);

      if (sit !== "nao_encontrado" && !campo.caixa) {
        card.appendChild(
          el("div", "campo-nota-rodape", "Inferido pela chave de acesso (sem caixa na página)")
        );
      }

      const caixaEl = mapaCaixas.get(campo.campo);
      if (caixaEl) {
        const ativar = () => caixaEl.classList.add("ativa");
        const desativar = () => caixaEl.classList.remove("ativa");
        card.addEventListener("mouseenter", ativar);
        card.addEventListener("mouseleave", desativar);
        caixaEl.addEventListener("mouseenter", ativar);
        caixaEl.addEventListener("mouseleave", desativar);
      }

      lista.appendChild(card);
    }
    layout.appendChild(lista);
    root.appendChild(layout);

    // Rodapé com fonte e duração
    const rodape = el("footer", "detalhe-rodape");
    const fonteLabel =
      nota.fonte === "texto"
        ? "Camada de texto do PDF"
        : nota.fonte === "ocr"
        ? "OCR (RapidOCR)"
        : nota.fonte || "Desconhecida";
    const spanFonte = el("span");
    spanFonte.append("Fonte: ");
    spanFonte.appendChild(el("strong", null, fonteLabel));

    const spanTempo = el("span");
    spanTempo.append("Tempo de processamento: ");
    spanTempo.appendChild(el("strong", null, formatarDuracao(item.duracao_ms)));

    rodape.appendChild(spanFonte);
    rodape.appendChild(spanTempo);
    root.appendChild(rodape);
  }

  function renderFolha(root, item) {
    const folha = item.folha || {};
    const limiar = typeof folha.limiar === "number" ? folha.limiar : 0.9;
    const confianca = Number(folha.confianca) || 0;
    const abaixoLimiar = confianca < limiar;

    const layout = el("div", "detalhe-folha-layout");

    // Topo: foto + diagnóstico principal
    const topoGrid = el("div", "folha-topo-grid");
    const quadro = el("div", "folha-foto-quadro");
    if (item.midia) {
      const img = el("img", "folha-foto-img");
      img.src = item.midia;
      img.alt = `Folha ${item.arquivo || ""}`;
      img.loading = "lazy";
      quadro.appendChild(img);
    } else {
      quadro.appendChild(el("p", "detalhe-vazio-texto", "Imagem indisponível."));
    }
    topoGrid.appendChild(quadro);

    const diagCard = el("div", "folha-diagnostico-card");
    diagCard.appendChild(el("span", "folha-diagnostico-kicker", "Diagnóstico principal"));
    diagCard.appendChild(el("h3", "folha-diagnostico-nome", folha.rotulo || folha.classe || "—"));

    const comp = el("div", "folha-limiar-comparacao");
    comp.append("Confiança ");
    comp.appendChild(el("strong", null, formatarPorcentagem(confianca, 1)));
    comp.append(" vs. limiar ");
    comp.appendChild(el("strong", null, formatarPorcentagem(limiar, 0)));
    comp.append(
      abaixoLimiar
        ? " — abaixo do corte, encaminhado para conferir."
        : " — acima do corte, aceito automaticamente."
    );
    diagCard.appendChild(comp);
    topoGrid.appendChild(diagCard);
    layout.appendChild(topoGrid);

    // Probabilidades das 4 classes com linha vertical do limiar
    const secProbs = el("section", "folha-secao");
    const cabProbs = el("div", "folha-secao-cabecalho");
    cabProbs.appendChild(el("h4", "folha-secao-titulo", "Probabilidades do classificador"));
    cabProbs.appendChild(
      el(
        "span",
        "folha-secao-subtitulo",
        `Linha vermelha marca o limiar (${formatarPorcentagem(limiar, 0)})`
      )
    );
    secProbs.appendChild(cabProbs);

    const listaProbs = el("div", "prob-lista");
    const probs = Array.isArray(folha.probabilidades) ? folha.probabilidades : [];
    const limiarPct = Math.max(0, Math.min(100, limiar * 100));

    for (const p of probs) {
      const prevista = p.classe === folha.classe;
      const linha = el(
        "div",
        `prob-linha${prevista ? " prevista" : ""}${
          prevista && abaixoLimiar ? " abaixo-limiar" : ""
        }`
      );
      linha.appendChild(el("span", "prob-rotulo", p.rotulo || p.classe));

      const trilho = el("div", "prob-trilho");
      const barra = el("div", "prob-barra");
      barra.style.width = `${Math.max(0, Math.min(100, (Number(p.p) || 0) * 100))}%`;
      trilho.appendChild(barra);

      const marcador = el("div", "prob-limiar");
      marcador.style.left = `${limiarPct}%`;
      marcador.title = `Limiar: ${formatarPorcentagem(limiar, 0)}`;
      trilho.appendChild(marcador);

      linha.appendChild(trilho);
      linha.appendChild(el("span", "prob-pct", formatarPorcentagem(p.p, 1)));
      listaProbs.appendChild(linha);
    }
    secProbs.appendChild(listaProbs);
    layout.appendChild(secProbs);

    // Linha de base genérica (ResNet-50 ImageNet)
    const baseline = Array.isArray(folha.linha_de_base) ? folha.linha_de_base : [];
    if (baseline.length > 0) {
      const secBase = el("section", "folha-secao");
      const cabBase = el("div", "folha-secao-cabecalho");
      cabBase.appendChild(
        el("h4", "folha-secao-titulo", "Linha de base genérica (ResNet-50 / ImageNet)")
      );
      cabBase.appendChild(
        el(
          "span",
          "folha-secao-subtitulo",
          "Rótulos genéricos mostram por que o modelo sem ajuste fino não resolve"
        )
      );
      secBase.appendChild(cabBase);

      const ul = el("ul", "baseline-lista");
      for (const b of baseline) {
        const li = el("li", "baseline-chip");
        li.appendChild(el("span", null, b.rotulo || "—"));
        li.appendChild(el("span", "baseline-score", formatarPorcentagem(b.score, 1)));
        ul.appendChild(li);
      }
      secBase.appendChild(ul);
      layout.appendChild(secBase);
    }

    root.appendChild(layout);

    // Rodapé com duração
    const rodape = el("footer", "detalhe-rodape");
    const spanModelo = el("span");
    spanModelo.append("Modelo: ");
    spanModelo.appendChild(el("strong", null, "EfficientNet-B0 (SojaTech)"));

    const spanTempo = el("span");
    spanTempo.append("Tempo de processamento: ");
    spanTempo.appendChild(el("strong", null, formatarDuracao(item.duracao_ms)));

    rodape.appendChild(spanModelo);
    rodape.appendChild(spanTempo);
    root.appendChild(rodape);
  }

  function renderTransitorioOuRejeitado(root, item) {
    const card = el("div", "detalhe-estado-card");

    if (item.motivo) {
      const motivo = el("div", "detalhe-motivo");
      const titulo = el("strong", null, "Motivo da rejeição: ");
      motivo.appendChild(titulo);
      motivo.append(item.motivo);
      card.appendChild(motivo);
    }

    if (item.midia) {
      const wrap = el("div", "detalhe-miniatura-wrap");
      const img = el("img", "detalhe-miniatura-img");
      img.src = item.midia;
      img.alt = `Miniatura de ${item.arquivo || "arquivo"}`;
      img.loading = "lazy";
      wrap.appendChild(img);
      card.appendChild(wrap);
    } else if (item.estado === "chegou" || item.estado === "processando") {
      card.appendChild(
        el(
          "p",
          "detalhe-vazio-texto",
          item.estado === "processando"
            ? "Processando arquivo na fila única; o resultado aparecerá automaticamente."
            : "Arquivo detectado na pasta de entrada, aguardando vez na fila."
        )
      );
    }

    root.appendChild(card);
  }

  function renderDetalhe(container, item) {
    if (!container) {
      return;
    }

    const assinatura = item ? JSON.stringify(item) : "__VAZIO__";
    if (
      container.firstElementChild &&
      container.__agroDetalheAssinatura === assinatura
    ) {
      return;
    }
    container.__agroDetalheAssinatura = assinatura;
    container.innerHTML = "";

    if (!item) {
      renderEstadoVazio(container);
      return;
    }

    const root = el("div", "detalhe-root");
    root.appendChild(renderCabecalho(item));

    if (item.resumo) {
      const classeExtra =
        item.estado === "conferir"
          ? " detalhe-resumo-conferir"
          : item.estado === "rejeitado"
          ? " detalhe-resumo-rejeitado"
          : "";
      root.appendChild(el("div", `detalhe-resumo-barra${classeExtra}`, item.resumo));
    }

    if (item.tipo === "nota" && item.nota) {
      renderNota(root, item);
    } else if (item.tipo === "folha" && item.folha) {
      renderFolha(root, item);
    } else {
      renderTransitorioOuRejeitado(root, item);
    }

    container.appendChild(root);
  }

  global.renderDetalhe = renderDetalhe;
  global.AgroDetalhe = {
    renderDetalhe,
    criarBadgeSituacao,
    situacaoInfo,
    formatarDuracao,
    formatarPorcentagem,
  };
})(window);
