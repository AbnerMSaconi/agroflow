# Resultados (gerado por scripts/evaluate.py)

## Notas fiscais — desenvolvimento

- 40 notas; acerto por campo **100.0%**, nota inteira certa **100.0%**
- digital vs. escaneada: {'digital': 1.0, 'escaneada': 1.0}
- por layout: {'compacto': 1.0, 'padrao': 1.0}
- confidence médio: certos 0.905 / errados None
- ECE 0.095; limiar sugerido 0.0

| campo | acerto | conf. média | conf. certos | conf. errados |
|---|---|---|---|---|
| cnpj_emitente | 1.000 | 0.850 | 0.85 | None |
| numero | 1.000 | 0.937 | 0.937 | None |
| data_emissao | 1.000 | 0.944 | 0.944 | None |
| valor_total | 1.000 | 0.891 | 0.891 | None |

## Notas fiscais — teste separado

- 40 notas; acerto por campo **100.0%**, nota inteira certa **100.0%**
- digital vs. escaneada: {'digital': 1.0, 'escaneada': 1.0}
- por layout: {'compacto': 1.0, 'padrao': 1.0, 'variante': 1.0}
- confidence médio: certos 0.907 / errados None
- ECE 0.093; limiar sugerido 0.0

| campo | acerto | conf. média | conf. certos | conf. errados |
|---|---|---|---|---|
| cnpj_emitente | 1.000 | 0.850 | 0.85 | None |
| numero | 1.000 | 0.940 | 0.94 | None |
| data_emissao | 1.000 | 0.947 | 0.947 | None |
| valor_total | 1.000 | 0.890 | 0.89 | None |

## Linha de base (rótulos genéricos), teste de laboratório

- 0.0% das imagens têm algum rótulo que identifica a doença
- 48.0% têm algum rótulo de planta/folha
- top-1 mais comuns: {'zucchini': 14, 'ear': 10, 'tree frog': 9, 'velvet': 9, 'stole': 6, 'vase': 6, 'pitcher': 6, 'conch': 6, 'cuirass': 5, 'head cabbage': 5}

## Linha de base (rótulos genéricos), teste de campo

- 2.4% das imagens têm algum rótulo que identifica a doença
- 76.4% têm algum rótulo de planta/folha
- top-1 mais comuns: {'ear': 63, 'zucchini': 9, 'cucumber': 5, 'African chameleon': 5, 'American chameleon': 4, 'tailed frog': 4, 'tree frog': 3, 'snorkel': 3, 'ant': 3, 'pot': 2}

## Classificador do produto (lab+campo), teste de laboratório

- 100 imagens; acurácia **99.0%**, F1 macro **0.990**
- confidence médio: certos 0.942 / errados 0.5455
- ECE 0.055
- limiar 0.95 (escolhido na validação): aceita 65.0%; erros barrados 1, erros que passam 0, acertos barrados 34

| classe | precisão | recall | F1 | conf. média |
|---|---|---|---|---|
| cercosporiose | 1.0 | 1.0 | 1.0 | 0.863 |
| ferrugem_comum | 0.962 | 1.0 | 0.98 | 0.988 |
| helmintosporiose | 1.0 | 0.96 | 0.98 | 0.911 |
| saudavel | 1.0 | 1.0 | 1.0 | 0.99 |

## Classificador do produto (lab+campo), teste de campo

- 127 imagens; acurácia **87.4%**, F1 macro **0.855**
- confidence médio: certos 0.900 / errados 0.75456875
- ECE 0.036
- limiar 0.95 (escolhido na validação): aceita 40.9%; erros barrados 15, erros que passam 1, acertos barrados 60

| classe | precisão | recall | F1 | conf. média |
|---|---|---|---|---|
| cercosporiose | 0.72 | 0.783 | 0.75 | 0.791 |
| ferrugem_comum | 0.87 | 1.0 | 0.93 | 0.962 |
| helmintosporiose | 0.946 | 0.828 | 0.883 | 0.864 |

## Disputa entre redes (validação; o teste não entra na escolha)

| rede | parâmetros (M) | F1 val. campo | F1 val. lab | treino (min) |
|---|---|---|---|---|
| efficientnet_b0 | 5.3 | 0.722 | 0.952 | 3.2 |
| efficientnet_v2_s | 21.5 | 0.743 | 0.945 | 4.6 |
| convnext_small | 50.2 | 0.750 | 0.971 | 2.3 |
| vit_b_16 **(escolhida)** | 86.9 | 0.779 | 0.959 | 5.5 |

# Tempo

- tempo médio por item (ms): {'local': {'folha_baseline': 10.8, 'folha_classificador': 15.0, 'nota': 529.7}}
