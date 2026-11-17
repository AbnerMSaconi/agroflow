# Conjuntos de notas fiscais

Todas as notas são fictícias, geradas por `sojatech_local/scripts/gen_danfes.py`.

| Pasta | Seed | Layouts | Papel |
|---|---|---|---|
| `pdf/` + `gabarito.csv` | 2026 | padrão, compacto | desenvolvimento |
| `teste/` | 7 | padrão, compacto, variante | **usado para ajustar o extrator** (rótulo `VALOR TOTAL DA NF-e`): não é mais um teste limpo |
| `validacao_s8/` | 8 | padrão, compacto, variante | desenvolvimento: o ajuste do valor com ponto decimal (OCR) saiu daqui |
| `holdout_s9/` | 9 | padrão, compacto, variante | **lacrado**: só se avalia uma vez, com o extrator congelado |

Regra: o extrator não é ajustado olhando o `holdout_s9`. Se for preciso mexer nele depois
da avaliação, o número deixa de valer e é preciso gerar outro holdout (outro seed).

Regerar um conjunto novo sem tocar nos existentes:

```
python scripts/gen_danfes.py --n 40 --seed 10 --variante --pasta holdout_s10
```
