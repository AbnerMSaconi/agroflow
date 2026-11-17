> **DESATUALIZADO.** Este relatório foi gravado em 16/11/2026 às 17:22, de uma rodada anterior da disputa
> (vencedora `convnext_small`). A rodada final (18:03) está em `results/disputa_redes.json` e em
> `models/leaf_classifier.json`: vencedora `vit_b_16`. Os números de teste vêm de `results/metricas.json` e
> `results/resumo.md`. Para o paper e para o produto, use esses arquivos, não os números abaixo.

# Relatório de entrega — classificador de folhas (rodada final)

Data da rodada: 2026-11-16. Commit de base: `afbfb8e` (branch `modelo-folhas`).
Dados brutos: `results/disputa_redes.json`; modelo do produto: `models/leaf_classifier.pt` e `.json`.

## Dados

Quatro classes de milho: cercosporiose, ferrugem_comum, helmintosporiose, saudavel.

| Conjunto | Origem | Treino | Validação | Teste |
|---|---|---|---|---|
| Laboratório | PlantVillage (CC BY-SA 3.0) | 1528 | 272 | 25 por classe |
| Campo | PlantDoc (CC BY 4.0), sem milho saudável | 183 | 55 | 127 |

Os dados foram regenerados nesta rodada com `scripts/prepare_leaves.py` e `scripts/prepare_campo.py`.
O conjunto de laboratório ficou idêntico ao versionado. No campo, uma foto
(`teste/cercosporiose/cercosporiose_campo_046.jpg`) foi recodificada com 1 byte de diferença,
e 3 linhas do manifesto mudaram.

## Protocolo da disputa

- Todas as redes treinam com o mesmo protocolo: 15 épocas, mesma semente, mesmo aumento de dados e
  mesmo lote efetivo, em uma GPU RTX 3090.
- A escolha usa o **F1 macro na validação de campo**. Se a diferença for menor que 0,02, vence a rede
  com menos parâmetros.
- O conjunto de teste não participa da escolha.

## Resultado

| Rede | Parâmetros (M) | F1 val. campo | Acurácia val. campo | F1 val. lab | Melhor época | Lote | Treino (min) |
|---|---|---|---|---|---|---|---|
| efficientnet_b0 | 5,3 | 0,722 | 0,782 | 0,952 | 9 | 32 | 2,7 |
| efficientnet_v2_s | 21,5 | 0,743 | 0,800 | 0,945 | 13 | 16 | 4,3 |
| **convnext_small** | 50,2 | 0,750 | 0,800 | **0,971** | 11 | 32 | 2,2 |
| vit_b_16 | 86,9 | **0,768** | 0,800 | 0,922 | 5 | 8 | 5,0 |

**Vencedora: `convnext_small`.** O `vit_b_16` teve o maior F1 no campo, mas ficou só 0,018 acima da
`convnext_small`, abaixo da margem de 0,02. Pelo critério de desempate, vence a rede menor. A
`convnext_small` também teve o melhor F1 no laboratório e o menor tempo de treino.

## Observações da execução

- A primeira tentativa caiu com `CUDA error: unspecified launch failure` durante o `vit_b_16`, sem
  gravar resultados. A segunda, com `CUDA_LAUNCH_BLOCKING=1`, rodou até o fim sem erro.
- A validação de campo tem só 55 fotos, então diferenças de poucos centésimos no F1 estão dentro do
  ruído. Esse é o motivo do critério de desempate.

## Vencedora no conjunto de teste

Medido depois da escolha, com `scripts/run_batch.py folhas` e `scripts/evaluate.py`
(detalhes em `results/resumo.md` e `results/metricas.json`).

| Teste | Imagens | Acurácia | F1 macro | ECE |
|---|---|---|---|---|
| Laboratório | 100 | 97,0% | 0,970 | 0,031 |
| Campo | 127 | 82,7% | 0,788 | 0,119 |

F1 por classe no campo: cercosporiose 0,591; ferrugem_comum 0,921; helmintosporiose 0,851.
A cercosporiose é o ponto fraco no campo (precisão 0,619, recall 0,565).

Com o limiar de confiança 0,95 (escolhido na validação), o modelo aceita 81,1% das fotos de campo:
barra 14 erros, deixa passar 8 e barra 10 acertos.
