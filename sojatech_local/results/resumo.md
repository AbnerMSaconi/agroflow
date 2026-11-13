# Resultados (gerado por scripts/evaluate.py)

## Notas fiscais — desenvolvimento

- 40 notas; acerto por campo **100.0%**, nota inteira certa **100.0%**
- digital vs. escaneada: {'digital': 1.0, 'escaneada': 1.0}
- por layout: {'compacto': 1.0, 'padrao': 1.0}
- confidence médio: certos 0.904 / errados None
- ECE 0.096; limiar sugerido 0.0

| campo | acerto | conf. média | conf. certos | conf. errados |
|---|---|---|---|---|
| cnpj_emitente | 1.000 | 0.850 | 0.85 | None |
| numero | 1.000 | 0.933 | 0.933 | None |
| data_emissao | 1.000 | 0.942 | 0.942 | None |
| valor_total | 1.000 | 0.891 | 0.891 | None |

## Notas fiscais — teste separado

- 40 notas; acerto por campo **91.9%**, nota inteira certa **67.5%**
- digital vs. escaneada: {'digital': 0.927, 'escaneada': 0.906}
- por layout: {'compacto': 1.0, 'padrao': 1.0, 'variante': 0.75}
- confidence médio: certos 0.908 / errados 0.0
- ECE 0.084; limiar sugerido 0.05

| campo | acerto | conf. média | conf. certos | conf. errados |
|---|---|---|---|---|
| cnpj_emitente | 1.000 | 0.850 | 0.85 | nan |
| numero | 1.000 | 0.940 | 0.94 | nan |
| data_emissao | 1.000 | 0.947 | 0.947 | nan |
| valor_total | 0.675 | 0.602 | 0.892 | 0.0 |

Erros (13):

| arquivo | campo | esperado | extraído | conf. | fonte |
|---|---|---|---|---|---|
| nota_001.pdf | valor_total | 2896.66 | nan | 0.0 | texto |
| nota_004.pdf | valor_total | 102439.15 | nan | 0.0 | texto |
| nota_005.pdf | valor_total | 11387.59 | nan | 0.0 | ocr |
| nota_010.pdf | valor_total | 32312.89 | nan | 0.0 | ocr |
| nota_015.pdf | valor_total | 2588.29 | nan | 0.0 | texto |
| nota_016.pdf | valor_total | 7530.51 | nan | 0.0 | texto |
| nota_017.pdf | valor_total | 24048.93 | nan | 0.0 | ocr |
| nota_022.pdf | valor_total | 484.98 | nan | 0.0 | texto |
| nota_026.pdf | valor_total | 62266.23 | nan | 0.0 | ocr |
| nota_032.pdf | valor_total | 16119.52 | nan | 0.0 | texto |
| nota_035.pdf | valor_total | 51958.20 | nan | 0.0 | texto |
| nota_036.pdf | valor_total | 69271.47 | nan | 0.0 | ocr |
| nota_038.pdf | valor_total | 10317.00 | nan | 0.0 | ocr |

## Linha de base (rótulos genéricos)

- 0.0% das imagens têm algum rótulo que identifica a doença
- 48.0% têm algum rótulo de planta/folha
- top-1 mais comuns: {'zucchini': 14, 'ear': 10, 'tree frog': 9, 'velvet': 9, 'stole': 6, 'vase': 6, 'pitcher': 6, 'conch': 6, 'cuirass': 5, 'head cabbage': 5}

## Classificador de folhas

- acurácia **95.0%**, F1 macro **0.950**
- confidence médio: certos 0.954 / errados 0.75198
- ECE 0.013; limiar sugerido 0.9

| classe | precisão | recall | F1 | conf. média |
|---|---|---|---|---|
| cercosporiose | 0.857 | 0.96 | 0.906 | 0.937 |
| ferrugem_comum | 1.0 | 1.0 | 1.0 | 0.971 |
| helmintosporiose | 0.955 | 0.84 | 0.894 | 0.874 |
| saudavel | 1.0 | 1.0 | 1.0 | 0.995 |

# Tempo

- tempo médio por item (ms): {'local': {'folha_baseline': 102.7, 'folha_classificador': 9.1, 'nota': 1328.3}}
