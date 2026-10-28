# Andamento do plano — atualizado em 26/10/2026

Legenda: ✅ feito · 🟡 pronto para rodar no GCP (código/script existe, falta executar) · ⬜ depende de você

Decisão: tudo roda localmente com substitutos de custo zero (`SOJATECH_BACKEND=local`).
O código GCP está escrito atrás da mesma interface; ligar o GCP é opcional e
só serve se a disciplina exigir os serviços de verdade ou para a comparação
"genérico vs. local" no relatório.

## Fase 0 — Setup e dados
- 🟡 Projeto GCP, créditos, orçamento com alerta, APIs, service account → `infra/setup_gcp.sh`
- ✅ Repositório Git com pastas (funções, avaliação, gabarito, relatório) — falta criar o remoto no GitHub
- ✅ 40 DANFEs (`data/invoices/pdf`), 26 digitais + 14 "escaneadas", 2 layouts
- ✅ Gabarito `data/invoices/gabarito.csv` (CNPJ emitente, número, data de emissão, valor total)
- ✅ Dados pessoais: notas 100% fictícias, nada a anonimizar
- ✅ 4 classes de milho do PlantVillage (3 doenças + saudável)
- ✅ 100 treino / 25 teste por classe, teste fixo em `data/leaves/test`

## Fase 1 — Notas fiscais
- 🟡 Processador Invoice Parser → criar no console; extrator pronto em `sojatech/invoices/docai_extractor.py`
- ✅ Script de extração (campo, valor, confidence) — local: `local_extractor.py`
- ✅ Rodado nas 40 notas e comparado campo a campo (`results/notas_comparacao.csv`)
- ⬜ Prints de onde o parser genérico erra na DANFE (precisa do Document AI)
- ⬜ Custom Extractor, se o Invoice Parser for mal

## Fase 2 — Folhas
- ✅ Linha de base (local: ResNet-50 ImageNet) — 0% das imagens com rótulo de doença; 🟡 Vision API
- ✅ Classificador treinado (local: EfficientNet-B0, 13 s na GPU) — 95% de acurácia no teste
- 🟡 Vertex AutoML: upload/dataset/treino/deploy/undeploy em `infra/vertex_train.sh`
- ✅ Plano B (modelo local) já é o padrão

## Fase 3 — Pipeline
- ✅ Bucket de entrada com `notas/` e `imagens/` (local) · 🟡 GCS
- ✅ Função com trigger de arquivo novo (watchdog) · 🟡 Cloud Function `cloud_function/main.py`
- ✅ Scripts das fases 1 e 2 reaproveitados como módulos (`sojatech/`)
- ✅ Tabela de resultados (SQLite, mesmo esquema do BigQuery)
- ✅ Rejeitados + log testados (extensão inválida, imagem corrompida)
- ✅ Ponta a ponta com 5 notas + 5 imagens
- ⬜ (Opcional) Natural Language

## Fase 4 — Avaliação
- ✅ `scripts/evaluate.py` (no lugar do notebook): tabelas, gráficos, LaTeX
- ✅ Limiar de confidence e erros barrados (`metricas.json`, gráficos `*_limiar.png`)
- ✅ Tempo por item; custo GCP estimado (preços de referência — **conferir antes de citar**)

## Fase 5 — Relatório
- ✅ Esqueleto + texto-base das 8 seções em `report/secoes/`, tabelas e figuras já ligadas
- ⬜ Colar no template do professor; compilar (não há LaTeX instalado aqui — use Overleaf ou MiKTeX)
- ⬜ Prints do console, link do repositório, fundamentação com referências

## Fase 6 — Apresentação
- ⬜ Slides, vídeo de reserva, ensaios

## Pontos de atenção
- O extrator local acerta 100% das notas, mas as regras foram ajustadas vendo esses layouts.
  Vale gerar um conjunto separado (outro seed/layout) só para teste antes de citar o número.
- O confidence do CNPJ é quase constante (0,85): informativo só quando o dígito verificador falha.
