# Resultados (gerado por scripts/evaluate.py)

Backend: `local`

## Notas fiscais

- 40 notas; acerto por campo **100.0%**, nota inteira certa **100.0%**
- digital vs. escaneada: {'digital': 1.0, 'escaneada': 1.0}
- confidence médio: certos 0.904 / errados None
- ECE 0.096; limiar sugerido 0.0

| campo | acerto | conf. média | conf. certos | conf. errados |
|---|---|---|---|---|
| cnpj_emitente | 1.000 | 0.850 | 0.85 | None |
| numero | 1.000 | 0.933 | 0.933 | None |
| data_emissao | 1.000 | 0.942 | 0.942 | None |
| valor_total | 1.000 | 0.891 | 0.891 | None |

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

## Tempo e custo

- tempo médio por item (ms): {'folha_baseline': 70.4, 'folha_classificador': 7.2, 'nota': 1258.7}
- estimativa mensal GCP (USD): {'document_ai': 20.0, 'vision_api': 7.5, 'vertex_endpoint_24x7': 1003.75}
