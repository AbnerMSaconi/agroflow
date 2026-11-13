# AgroFlow: classificador de folhas para laboratório e campo

Desenho, 13/11/2026. Situação: aprovado em 13/11/2026. Vem antes das telas
(`2026-11-13-agroflow-telas-design.md`), porque a amostra da demo e os números do
relatório dependem do modelo.

## Intenção

O classificador atual (EfficientNet-B0, 100 fotos por classe, 13 s de treino) acerta 95%
no teste do PlantVillage, mas só foi medido em foto de laboratório. A apresentação vai
rodar numa RTX 3090 (acesso remoto ou gravação), então dá para usar uma rede bem maior.

Queremos um modelo melhor **e** medido onde importa para a SojaTech: em foto de campo.
O relatório já diz que "fotos de campo serão mais difíceis"; aqui isso vira número. O
mais provável é o modelo treinado só com laboratório errar muito mais no campo e manter
a confiança alta. Essa é a tese do trabalho (confiança não é acerto) na forma mais forte.
Depois, com fotos de campo no treino, medimos quanto do acerto volta.

## Objetivos

- Uma rede maior, escolhida por disputa justa entre candidatas, aproveitando a GPU:
  precisão mista, lotes maiores e resolução maior quando a rede pede.
- Dois modelos com a mesma rede:
  - **lab**: treinado só com o PlantVillage, para medir a queda no campo;
  - **lab+campo**: com fotos de campo no treino. É o modelo do produto e das telas.
- Dois testes: o de laboratório de hoje (100 fotos, sem mudança) e um teste de campo novo.
- Avaliação dos dois modelos nos dois testes: acerto, F1 por classe, matriz de confusão,
  confiança dos acertos e dos erros, ECE e efeito do limiar.
- Tudo reprodutível a partir do repositório: quem clonar (a 3090, o Colab) treina e
  avalia sem baixar nada à mão.

## Não objetivos

- Calibrar a confiança (escala de temperatura). Fica como trabalho futuro na discussão.
- Soja doente: o PlantDoc só tem soja saudável.
- Mais de uma folha por foto (detecção), outras culturas, explicabilidade (Grad-CAM).
- Modelos de fundação com dependência nova (DINOv2): abordagem descartada.
- Mudar a extração de notas fiscais.

## Antiobjetivos (falha mesmo que funcione)

- Escolher a rede, a época ou o limiar olhando o teste.
- A mesma foto, ou uma quase igual, aparecer no treino e no teste de campo.
- Mudar o teste de laboratório e perder a comparação com o modelo de hoje.
- A demo usar um modelo diferente do que gerou os números do relatório.

## Restrições

- Esta máquina: RTX 5060 com 8 GB. Apresentação: RTX 3090 com 24 GB. Python 3.12 e
  torch 2.11 (cu128) nas duas.
- Só redes do torchvision (sem biblioteca nova).
- PlantDoc: licença CC BY 4.0, exige atribuição. PlantVillage: citar a fonte
  (Hughes e Salathé, 2015), como o trabalho já faz.
- O arquivo do modelo pode passar de 300 MB e não cabe no Git.

## Abordagens

1. **Comparar redes prontas do torchvision (escolhida pelo usuário).** As candidatas são
   treinadas com o mesmo protocolo, e vence a melhor na validação de campo. Não precisa
   de dependência nova.
2. **Modelo de fundação (DINOv2).** Descartada: dependência nova e pesos baixados da
   internet na primeira execução, um risco na 3090.
3. **Só mais fotos na EfficientNet-B0.** Descartada: não aproveita a 3090.

## Desenho

### Dados

**Laboratório (PlantVillage, 4 classes)**

- **Teste:** as mesmas 25 fotos por classe de hoje (`data/leaves/test`), sem mudança.
- **Treino:** passa de 100 para 450 fotos por classe. A cercosporiose tem 488 fora do
  teste, e por isso o teto é 450. Com a mesma semente e a mesma ordem, as 100 fotos de
  hoje continuam no treino com o mesmo nome; as novas entram depois delas.
- **Validação:** 15% do treino, fixa e listada num manifesto. Hoje ela é sorteada a cada
  treino.
- `prepare_leaves.py` passa a não apagar a pasta de campo e a escrever o manifesto.
- As fotos novas são versionadas (~20 MB), para a 3090 e o Colab não precisarem de
  `_downloads/`.

**Campo (PlantDoc, 3 classes de milho, sem saudável)**

| Pasta do PlantDoc | Classe | Fotos |
|---|---|---|
| Corn Gray leaf spot | cercosporiose | 68 |
| Corn leaf blight | helmintosporiose | 192 |
| Corn rust leaf | ferrugem_comum | 116 |

- Um script novo (`scripts/prepare_campo.py`) baixa só essas pastas, com checkout
  esparso do repositório do PlantDoc (~124 MB em `_downloads/`).
- **Remoção de repetidas:** hash perceptual (dHash de 64 bits, feito com PIL). Fotos a
  até 4 bits de distância contam como a mesma, e fica uma só. O PlantDoc tem fotos
  repetidas entre o treino e o teste originais, por isso a divisão original não é usada.
- Divisão nova, estratificada por classe e com semente fixa: 50% treino, 15% validação
  e 35% teste (perto de 130 fotos de teste).
- As fotos são reduzidas para no máximo 512 px no lado maior e versionadas em
  `data/leaves/campo/<treino|val|teste>/<classe>/` (~15 MB), com um `FONTE.md` de
  atribuição e o manifesto (arquivo de origem, hash, partição).

### Treino (`scripts/train_leaf_classifier.py`, reescrito)

- **Argumentos:** `--rede {efficientnet_b0, efficientnet_v2_s, convnext_small, vit_b_16}`,
  `--dados {lab, lab+campo}`, `--epocas`, `--lote`, `--saida`.
- **Pré-processamento:** a resolução e a normalização vêm dos pesos de cada rede no
  torchvision. A ViT-B/16 usa os pesos SWAG, em 384 px.
- **Otimização:** AdamW com taxa em cosseno e aquecimento, precisão mista, `channels_last`
  e DataLoader com vários processos. O lote padrão cabe em 8 GB; na 3090 pode ser maior.
- **Aumento de dados:** o de hoje (recorte, espelhamento, cor) mais efeitos que imitam o
  campo: TrivialAugment, desfoque leve e apagamento aleatório.
- **Mistura de lab e campo:** amostragem ponderada para que as fotos de campo sejam
  cerca de 1/3 de cada época. Sem isso, as ~190 fotos de campo sumiriam entre as ~1.530
  de laboratório.
- **Escolha da época:**
  - o modelo lab fica com a época de melhor F1 macro na validação de laboratório e nunca
    vê foto de campo;
  - o modelo lab+campo fica com a de melhor F1 macro na validação de campo.
- **Saída:** `models/leaf_classifier.pt` (lab+campo, o do produto) e
  `models/leaf_classifier_lab.pt`. Cada um guarda a rede, as classes, a resolução e os
  pesos, mais um `.json` com histórico, tempo e GPU.

### Disputa entre redes

- **Candidatas:** EfficientNet-B0 (referência, a de hoje), EfficientNetV2-S,
  ConvNeXt-Small e ViT-B/16 (SWAG).
- Cada uma é treinada com dados lab+campo, a mesma semente, o mesmo número de épocas e o
  mesmo aumento de dados. O lote pode variar com a memória, mas o lote efetivo é igual
  para todas, usando acumulação de gradiente.
- Vence a de maior F1 macro na validação de campo. Se a diferença ficar abaixo de 2
  pontos, vence a mais leve.
- O resultado fica em `results/disputa_redes.json`, mais uma tabela para o relatório.
  O teste não entra na escolha.

### Avaliação

- `run_batch.py folhas` roda a linha de base e os dois modelos nas validações e nos
  testes de laboratório e de campo.
  - Nome gravado: `<conjunto>/<partição>/<classe>/<arquivo>`, por exemplo
    `campo/teste/ferrugem_comum/foto.jpg`.
  - Tipo gravado: `folha_classificador` (lab+campo), `folha_classificador_lab` e
    `folha_baseline`.
- `evaluate.py`, para cada modelo e cada conjunto: acerto, F1 macro e por classe, matriz
  de confusão, confiança média dos acertos e dos erros, ECE e efeito do limiar.
- **Limiar:** escolhido na validação de campo, com o mesmo critério de hoje (menor
  limiar com precisão ≥ 98% entre os aceitos), e aplicado nos testes.
  `metricas.json → classificador.limiar_escolhido` passa a ser esse valor, que o produto
  usa. As notas não mudam.
- **Saídas novas:**
  - uma tabela comparando lab e campo para os dois modelos;
  - a matriz de confusão e a calibração no campo para o modelo do produto;
  - a tabela da disputa;
  - a linha de base também no campo.

### Integração com o produto

- `leaves/local_models.py` lê do arquivo a rede e a resolução e monta o
  pré-processamento certo. Por fora, `classify()` não muda.
- As telas usam o modelo lab+campo. A amostra do "Enviar exemplos" é escolhida de novo
  depois, com casos reais de acerto, erro e confiança baixa, agora com fotos de campo
  entre elas.

### Onde roda

- A disputa, o treino final e a avaliação rodam nesta máquina, onde consigo executar e
  conferir. Se a rede vencedora não couber para treinar em 8 GB, o treino final roda na
  3090 com o mesmo script.
- A 3090 não retreina: usa o arquivo do modelo final, para a demo usar exatamente o
  modelo dos números do relatório. O arquivo é copiado para lá. O jeito (release no
  GitHub, que exige instalar o `gh`; Google Drive; ou a própria ferramenta de acesso
  remoto) se decide quando o modelo existir. O `.json` do modelo guarda um hash do
  arquivo, e o app avisa se o modelo carregado não for o avaliado.

### Relatório

- As tabelas e figuras novas são geradas pelo `evaluate.py` em `report/tabelas` e
  `report/figuras`.
- O texto de três seções vai ficar desatualizado: a 4 (dados e rede), a 5 (resultados no
  campo) e a 7 (a limitação de campo, agora medida).

### Verificação

- `prepare_campo.py`: contagem por classe e por partição; nenhuma repetida entre
  partições; teste de laboratório idêntico ao de hoje (mesmo hash por arquivo).
- Treino: teste rápido de 1 época com 2 fotos por classe para cada rede; o arquivo
  gerado carrega no `local_models`.
- Avaliação: `evaluate.py` roda com os dois modelos, e os números das notas não mudam.

## Decisões minhas para conferir

1. Validações fixas por manifesto, em vez de sorteadas a cada treino.
2. Campo dividido em 50% / 15% / 35%, por classe, depois de tirar as repetidas.
3. Fotos de campo reduzidas para 512 px e versionadas; treino de laboratório ampliado para
   450 por classe, também versionado.
4. As fotos de campo pesam cerca de 1/3 de cada época.
5. Vence a disputa a melhor no F1 macro da validação de campo; empate abaixo de 2 pontos
   vai para a mais leve.
6. O modelo lab nunca vê foto de campo, nem para escolher a época.
7. O limiar do produto sai da validação de campo, com o critério de hoje.
8. Tudo roda aqui; a 3090 recebe uma cópia do modelo final, conferida por hash.

## A critério de quem constrói

- Taxas de aprendizado, número de épocas e lote de cada rede, desde que o protocolo seja
  o mesmo para todas na disputa.
- Nomes de funções e de arquivos auxiliares.
- Formato das tabelas novas, dentro do estilo das atuais.
