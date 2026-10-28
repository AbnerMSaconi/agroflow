# Plano do Projeto — SojaTech (Workshop P2)

Oct 24, 2026 · @Abner Saconi

## Visão geral

O projeto entrega um pipeline único no GCP que resolve os dois gargalos da SojaTech: extrai campos de notas fiscais com Document AI e classifica folhas com pragas com Vision API e Vertex AI. A Natural Language API entra só se sobrar tempo.

**Escopo obrigatório**

- Document AI extraindo campos estruturados de notas fiscais em PDF
- Vision API como linha de base e Vertex AI AutoML como classificador treinado para folhas
- Pipeline orientado a eventos: Cloud Storage → Cloud Function → APIs → BigQuery
- Avaliação com gabarito próprio: confidence score do modelo comparado com precisão, recall e F1 medidos

**Escopo opcional**

- Natural Language API classificando chamados ou observações de fornecedores
- Dashboard simples no Looker Studio sobre a tabela de resultados

**Premissas**

- Prazo assumido de 4 semanas, de 26/10 a 22/11. Se a data da P2 for outra, as semanas encolhem ou esticam na mesma proporção.
- Conta GCP com créditos de avaliação ou de estudante. O treino no Vertex AI é o único item com custo relevante.
- Entregáveis: código num repositório Git, relatório no template LaTeX do professor e apresentação com demo.

## Fase 0 — Setup e dados (semana 1)

A fase termina quando o projeto GCP está pronto e os dois conjuntos de dados estão rotulados. Os dados demoram mais do que o setup, então comece por eles.

**Infraestrutura**

- [ ] Criar o projeto GCP e ativar créditos de avaliação ou de estudante
- [ ] Configurar um orçamento com alerta no Cloud Billing antes de qualquer outra coisa
- [ ] Ativar as APIs: Document AI, Vision, Vertex AI, Cloud Functions, Cloud Storage, Pub/Sub, BigQuery, Natural Language
- [ ] Criar uma Service Account para o pipeline com papéis mínimos (leitura no bucket, uso das APIs, escrita no BigQuery)
- [ ] Criar o repositório Git com pastas para funções, notebooks de avaliação, dados de gabarito e relatório

**Dados de notas fiscais**

- [ ] Juntar 30 a 50 PDFs de DANFE: notas próprias, exemplos públicos ou notas fictícias geradas
- [ ] Montar uma planilha de gabarito com os campos esperados de cada nota: CNPJ do emitente, número, data de emissão, valor total
- [ ] Remover dados pessoais de notas reais antes de subir para a nuvem

**Dados de folhas**

- [ ] Escolher 3 ou 4 classes de um dataset público (ex.: PlantVillage), de preferência com uma classe saudável
- [ ] Separar cerca de 100 imagens por classe para treino e um conjunto de teste fixo de 20 a 30 por classe
- [ ] Guardar o conjunto de teste à parte: ele avalia tanto a Vision API quanto o modelo do Vertex

## Fase 1 — Notas fiscais com Document AI (semana 1–2)

A fase termina com um script que recebe um PDF e devolve os campos extraídos em JSON, já medido contra o gabarito.

- [ ] Criar um processador *Invoice Parser* e testar com 5 notas no console
- [ ] Escrever o script de extração (Python ou C#), salvando campo, valor e confidence de cada nota
- [ ] Rodar nas 30 a 50 notas e comparar com o gabarito, campo a campo
- [ ] Registrar onde o parser genérico erra no layout da DANFE, com prints
- [ ] Se o acerto ficar baixo, testar um *Custom Extractor* treinado com parte das notas e comparar os dois

O ponto do relatório aqui é mostrar a diferença entre um parser pensado para faturas estrangeiras e o documento brasileiro.

## Fase 2 — Folhas com Vision API e Vertex AI (semana 2)

A fase termina com dois resultados sobre o mesmo conjunto de teste: a linha de base da Vision API e o modelo treinado no Vertex AI.

**Linha de base: Vision API**

- [ ] Rodar *label detection* no conjunto de teste e guardar os rótulos e scores devolvidos
- [ ] Mostrar que os rótulos são genéricos ("leaf", "plant") e não separam as pragas

**Classificador: Vertex AI AutoML**

- [ ] Subir as imagens de treino num bucket com o CSV de rótulos e criar o dataset de classificação
- [ ] Treinar com o menor orçamento de horas de nó permitido e acompanhar o custo no Billing
- [ ] Exportar a avaliação do console: precisão, recall e matriz de confusão
- [ ] Implantar num endpoint só durante testes e demo, e remover a implantação logo depois, porque endpoint ligado cobra por hora

**Plano B se o crédito apertar**

- [ ] Exportar o modelo para rodar localmente, ou usar só a Vision API e discutir a limitação como resultado

## Fase 3 — Pipeline integrado (semana 2–3)

A fase termina quando subir um arquivo no bucket basta para o resultado aparecer no BigQuery, sem nenhum passo manual.

&#91;embedded content: arquitetura do pipeline · 6 serviços\]

A Cloud Function é o único ponto de entrada: ela olha a extensão do arquivo e chama a API correspondente. A linha tracejada é a parte opcional.

- [ ] Criar o bucket de entrada com pastas para notas e imagens
- [ ] Escrever a Cloud Function com trigger de finalização de objeto no bucket
- [ ] Reaproveitar os scripts das Fases 1 e 2 como módulos dentro da função
- [ ] Criar a tabela no BigQuery: arquivo, tipo, campo ou classe, valor, confidence, data de processamento
- [ ] Tratar erros: arquivo inválido vai para uma pasta de rejeitados e gera log
- [ ] Testar ponta a ponta com 5 notas e 5 imagens
- [ ] (Opcional) Adicionar a rota de texto para a Natural Language API

## Fase 4 — Avaliação e métricas (semana 3)

O diferencial do trabalho é mostrar que o confidence score do modelo e a precisão medida contra o gabarito são números diferentes.

| Componente | Unidade avaliada | Métricas | Comparação para o relatório |
| --- | --- | --- | --- |
| Document AI | Cada campo de cada nota | Acerto por campo, acerto da nota inteira | Confidence médio dos campos certos vs. dos errados |
| Vision API | Cada imagem de teste | Se algum rótulo identifica a praga | Score alto mesmo com rótulo genérico |
| Vertex AI | Cada imagem de teste | Precisão, recall, F1 por classe, matriz de confusão | Confidence vs. acerto real por classe |
| Natural Language (opcional) | Cada chamado | Acerto de categoria e sentimento | Score vs. rótulo manual |

- [ ] Escrever um notebook que lê o BigQuery e o gabarito e gera as tabelas e gráficos acima
- [ ] Escolher um limiar de confidence e mostrar quantos erros ele teria barrado
- [ ] Registrar custo e tempo de processamento por documento e por imagem

## Fase 5 — Documentação no template LaTeX (semana 3–4)

Escreva o relatório em paralelo desde a semana 2: cada fase concluída vira uma seção, e a semana 4 fica só para revisão.

1. Introdução: o problema da SojaTech e os dois processos manuais
2. Fundamentação: OCR, extração de documentos, classificação de imagens, AutoML, métricas de avaliação
3. Arquitetura: o diagrama do pipeline, serviços usados e papel de cada um, IAM
4. Implementação
   1. Document AI: processador, script, problemas com a DANFE
   2. Vision API e Vertex AI: linha de base, dataset, treino, endpoint
   3. Pipeline: trigger, roteamento por tipo, gravação no BigQuery
5. Resultados: tabelas e gráficos da Fase 4, com a comparação entre confidence e precisão
6. Custos: quanto cada serviço consumiu e uma estimativa para o volume real da empresa
7. Discussão e limitações: tamanho do gabarito, dados sintéticos, viés do dataset de folhas
8. Conclusão e trabalhos futuros

- [ ] Guardar prints do console a cada passo, porque refazer depois custa tempo e crédito
- [ ] Colocar o link do repositório no relatório

## Fase 6 — Apresentação e demo (semana 4)

A apresentação conta a história em uma linha: dois processos manuais viram um pipeline, e os números mostram o quanto dá para confiar nele.

**Roteiro sugerido (cerca de 15 minutos)**

1. Problema da SojaTech — 1 slide
2. Arquitetura — o diagrama do pipeline
3. Demo ao vivo: subir uma nota e uma folha no bucket e mostrar o resultado chegando no BigQuery
4. Resultados: acerto do Document AI por campo e matriz de confusão do Vertex
5. Confidence vs. precisão: o slide que diferencia o trabalho
6. Custos e limitações
7. Conclusão

**Preparação**

- [ ] Gravar um vídeo curto da demo como reserva, caso a rede ou o endpoint falhem na hora
- [ ] Implantar o endpoint do Vertex só no dia da apresentação e remover depois
- [ ] Ensaiar duas vezes cronometrando
- [ ] Preparar respostas para perguntas prováveis: por que não usar um LLM multimodal, quanto custaria em produção, como tratar notas ilegíveis

## Cronograma, riscos e checklist final

O marco que importa é o pipeline funcionando ponta a ponta no fim da semana 3; se ele escorregar, a primeira coisa a cortar é a Natural Language.

&#91;embedded content: cronograma · 4 semanas, 7 frentes\]

O relatório começa na semana 2 e corre em paralelo, para a última semana ser só revisão e ensaio.

**Riscos**

| Risco | Sinal de alerta | Resposta |
| --- | --- | --- |
| Crédito acaba no treino do Vertex | Alerta de orçamento acima de 50% | Treinar com menos horas de nó ou exportar o modelo e rodar localmente |
| Endpoint esquecido ligado | Custo diário subindo sem uso | Remover a implantação após cada sessão de teste |
| Invoice Parser erra muito na DANFE | Acerto por campo abaixo de 50% | Testar o Custom Extractor e tratar o erro como achado do relatório |
| Poucas notas reais para o gabarito | Menos de 30 PDFs na semana 1 | Gerar DANFEs fictícias com dados inventados |
| Demo falha ao vivo | Rede instável no local | Usar o vídeo de reserva |

**Checklist final de entrega**

- [ ] Repositório com README explicando como rodar o pipeline
- [ ] Relatório compilado no template do professor, com link do repositório
- [ ] Slides com o diagrama, os resultados e o slide de confidence vs. precisão
- [ ] Vídeo de reserva da demo
- [ ] Endpoint do Vertex removido e recursos sem uso desligados depois da apresentação
