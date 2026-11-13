# Fotos de laboratório: PlantVillage

As fotos de `train/` e `test/` vêm do PlantVillage, publicado sob a licença Creative Commons
Atribuição-CompartilhaIgual 3.0 (CC BY-SA 3.0): https://github.com/spMohanty/PlantVillage-Dataset
(licença declarada no cartão do conjunto em https://huggingface.co/datasets/mohanty/PlantVillage).
Por ser CompartilhaIgual, estas fotos continuam sob CC BY-SA 3.0 aqui.

Mohanty, S. P.; Hughes, D. P.; Salathé, M. Using deep learning for image-based plant disease
detection. Frontiers in Plant Science, v. 7, 2016. DOI: 10.3389/fpls.2016.01419.

Usamos só as quatro pastas de milho de `raw/color`:

| Pasta do PlantVillage | Classe aqui |
|---|---|
| Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot | cercosporiose |
| Corn_(maize)___Common_rust_ | ferrugem_comum |
| Corn_(maize)___Northern_Leaf_Blight | helmintosporiose |
| Corn_(maize)___healthy | saudavel |

Alterações feitas por `sojatech_local/scripts/prepare_leaves.py`: as fotos são copiadas sem
mudança no conteúdo, só renomeadas (`<classe>_<nnn>.jpg`). Por classe, um sorteio com semente
fixa separa 25 fotos de teste e 450 de treino, das quais 15% (fixas) são a validação. O
`manifesto_lab.csv` registra a partição de cada arquivo.

As fotos de campo (`campo/`) têm outra origem, descrita em `campo/FONTE.md`.
