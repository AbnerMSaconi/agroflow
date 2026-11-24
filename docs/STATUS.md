# Andamento do plano — atualizado em 23/11/2026

Legenda: ✅ feito · 🟡 escrito mas não executado · ⬜ pendente

**Situação:** o pipeline roda de ponta a ponta no `sojatech_local` (tela web, local e Docker com
GPU) e os dois serviços do Google foram executados de verdade pelos labs do Skills Boost
(Document AI no GSP1139, Vision API no GSP037). O pipeline completo no GCP (Cloud Storage, Cloud
Function, BigQuery, Vertex AI) continua escrito e **não executado**. Como rodar tudo:
[GUIA_LOCAL.md](GUIA_LOCAL.md) e [GUIA_CLOUD.md](GUIA_CLOUD.md).

## Fase 0 — Setup e dados
- ✅ Repositório: github.com/AbnerMSaconi/agroflow (branch única: `main`)
- ✅ 40 DANFEs fictícias com gabarito, conjuntos separados (desenvolvimento, validação, teste e
  `holdout_s9` lacrado; ver `data/invoices/CONJUNTOS.md`)
- ✅ Folhas de milho (4 classes): fotos de laboratório (PlantVillage) e de campo
- ❌ Conta GCP de estudante: não saiu; usamos labs do Skills Boost
- 🟡 Projeto GCP próprio com orçamento: `sojatech_cloud/infra/setup_gcp.sh`

## Fase 1 — Notas fiscais
- ✅ Extrator local (PyMuPDF + RapidOCR + regras por rótulo), congelado antes do holdout
- ✅ Layout novo, antes de corrigir as regras: 91,9% por campo e 67,5% por nota (13 erros, todos
  campo vazio com confidence 0)
- ✅ Holdout `holdout_s9` (40 notas): extrator local 40/40
- ✅ Document AI Invoice Parser (lab GSP1139): 40/40 no holdout, uma única rodada
- ✅ Document AI mais conservador no confidence (0,623 a 0,844) que o local (0,850 a 0,945)

## Fase 2 — Folhas
- ✅ Disputa de quatro arquiteturas na validação; escolhido o ViT-B/16
- ✅ ViT-B/16: 99,0% no laboratório e 87,4% no campo
- ✅ Linha de base ResNet-50 e Vision API (lab GSP037, 227 imagens): rótulos genéricos com score
  alto, não é diagnóstico
- 🟡 Vertex AI AutoML (`sojatech_cloud/infra/vertex_train.sh`): não executado, treino mínimo de 8
  horas de nó

## Fase 3 — Pipeline e aplicação
- ✅ Pipeline local com pasta monitorada (watchdog), tabela SQLite e rejeitados com log
- ✅ Tela web (`/prod` e `/press`) com fila única: aceito, conferir, rejeitado
- ✅ Docker (CPU e GPU) com NVIDIA Container Toolkit; 86 de 88 testes passam no container (os 2
  restantes precisam de `git`, ausente na imagem)
- ✅ Correção do aquecimento do OCR em `fluxo.py`
- 🟡 Cloud Storage + Cloud Function + BigQuery: `sojatech_cloud/cloud_function/` e `infra/`
- ⬜ (Opcional) Natural Language API e painel no Looker Studio

## Fase 4 — Avaliação
- ✅ `sojatech_local/scripts/evaluate.py`: métricas, gráficos e tabelas
- ✅ Limiar de confidence 0,95: laboratório 65,0% automático e zero erros passando; campo 40,9%
  automático, barra 15 de 16 erros, 59,1% vão para revisão
- ✅ Comparação Google vs. local no holdout (`sojatech_cloud/scripts/gera_tabelas_cloud.py`)
- ✅ Tempos locais (RTX 3090): 530 ms por nota, 10,8 ms (ResNet-50), 15,0 ms (ViT-B/16)
- ✅ Consumo nos labs: 6 créditos (1 no GSP1139, 5 no GSP037)
- ⬜ Fotos de milho saudável em campo, para medir falsos positivos

## Fase 5 — Relatório
- ✅ Paper no template elsarticle, mantido no **Overleaf** (`report/` saiu do git em 23/11)
- ⬜ Conferir prints, referências e a correção feita no Overleaf antes de entregar

## Fase 6 — Apresentação
- ✅ Roteiro de fala e slides de 14 páginas (locais, fora do git)
- ⬜ Ensaios e vídeo de reserva

## Pontos de atenção
- Só o `holdout_s9` mede generalização: os conjuntos de desenvolvimento, validação e teste inicial
  deixaram de ser independentes depois que as regras foram ajustadas olhando seus erros.
- O gabarito das DANFEs é sintético, o que explica parte do 100% no holdout.
- O conjunto de campo não tem milho saudável.
- Os guias de execução do GCP próprio (seção 7 do `GUIA_CLOUD.md`) não foram testados.
