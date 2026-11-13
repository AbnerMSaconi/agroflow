# Andamento do plano — atualizado em 13/11/2026

Legenda: ✅ feito · 🟡 pronto no `sojatech_cloud`, mas não executado (sem GCP) · ⬜ depende de você

**13/11/2026: o GCP saiu do plano.** A conta de estudante não ficou disponível. O
repositório foi dividido em dois projetos:

- `sojatech_local/`: o que roda o trabalho, na máquina ou no Colab
  (`sojatech_local/notebooks/agroflow_colab.ipynb`).
- `sojatech_cloud/`: o código do GCP (Document AI, Vision, Vertex, BigQuery,
  Cloud Function), arquivado e nunca executado.

O enunciado pedia Vision API, Vertex AI ou Document AI de verdade: isso agora é uma
limitação a tratar no relatório. Os itens 🟡 abaixo continuam prontos no
`sojatech_cloud`, mas ficam parados.

## Fase 0 — Setup e dados
- 🟡 Projeto GCP, créditos, orçamento com alerta, APIs, service account → `sojatech_cloud/infra/setup_gcp.sh`
- ✅ Repositório Git: github.com/AbnerMSaconi/agroflow (privado)
- ❌ Conta GCP de estudante: não saiu (13/11)
- ✅ 40 DANFEs (`data/invoices/pdf`), 26 digitais + 14 "escaneadas", 2 layouts
- ✅ Gabarito `data/invoices/gabarito.csv` (CNPJ emitente, número, data de emissão, valor total)
- ✅ Dados pessoais: notas 100% fictícias, nada a anonimizar
- ✅ 4 classes de milho do PlantVillage (3 doenças + saudável)
- ✅ 100 treino / 25 teste por classe, teste fixo em `data/leaves/test`

## Fase 1 — Notas fiscais
- 🟡 Processador Invoice Parser → criar no console; extrator pronto em `sojatech_cloud/agroflow/invoices/docai_extractor.py`
- ✅ Script de extração (campo, valor, confidence) — local: `local_extractor.py`
- ✅ Rodado nas 40 notas e comparado campo a campo (`sojatech_local/results/notas_comparacao.csv`)
- ✅ Conjunto de teste separado (`data/invoices/teste`, seed 7 + layout "variante" nunca visto):
  91,9% por campo, 67,5% nota inteira; os 13 erros são o valor total do layout novo, todos
  devolvidos vazios (confidence 0), nenhum valor errado com confidence alto
- ⬜ Prints de onde o parser genérico erra na DANFE (precisa do Document AI)
- ⬜ Custom Extractor, se o Invoice Parser for mal

## Fase 2 — Folhas
- ✅ Linha de base (local: ResNet-50 ImageNet) — 0% das imagens com rótulo de doença; 🟡 Vision API
- ✅ Classificador treinado (local: EfficientNet-B0, 13 s na GPU) — 95% de acurácia no teste
- 🟡 Vertex AutoML: upload/dataset/treino e avaliação no teste por batch prediction (sem endpoint)
  — notebook B5–B7 ou `sojatech_cloud/infra/vertex_train.sh`
- ✅ Plano B (modelo local) já é o padrão

## Fase 3 — Pipeline
- ✅ Bucket de entrada com `notas/` e `imagens/` (local) · 🟡 GCS
- ✅ Função com trigger de arquivo novo (watchdog) · 🟡 Cloud Function `sojatech_cloud/cloud_function/main.py`
- ✅ Scripts das fases 1 e 2 reaproveitados como módulos (`sojatech_local/agroflow/`)
- ✅ Tabela de resultados (SQLite, mesmo esquema do BigQuery)
- ✅ Rejeitados + log testados (extensão inválida, imagem corrompida)
- ✅ Ponta a ponta com 5 notas + 5 imagens
- ⬜ (Opcional) Natural Language

## Fase 4 — Avaliação
- ✅ `sojatech_local/scripts/evaluate.py`: tabelas, gráficos, LaTeX
- 🟡 Comparação Google vs. local nos mesmos testes (`report/tabelas/comparacao_backends.tex`,
  testada com dados simulados; falta rodar com os resultados reais do GCP)
- ✅ Limiar de confidence e erros barrados (`sojatech_local/results/metricas.json`, gráficos `*_limiar.png`)
- ✅ Tempo por item · 🟡 custo GCP estimado: agora só no `sojatech_cloud/scripts/evaluate.py`
  (a `report/tabelas/custos.tex` atual é da versão anterior)

## Fase 5 — Relatório
- ✅ Esqueleto + texto-base das 8 seções em `report/secoes/`, tabelas e figuras já ligadas
- ⬜ Colar no template do professor; compilar (não há LaTeX instalado aqui — use Overleaf ou MiKTeX)
- ⬜ Prints do console, link do repositório, fundamentação com referências

## Fase 6 — Apresentação
- ⬜ Slides, vídeo de reserva, ensaios

## Pontos de atenção
- O extrator local acerta 100% das notas de desenvolvimento, mas as regras foram ajustadas vendo
  esses layouts. Cite o número do conjunto de teste (91,9% por campo) e não ajuste o extrator
  olhando o teste.
- O confidence do CNPJ é quase constante (0,85): informativo só quando o dígito verificador falha.
