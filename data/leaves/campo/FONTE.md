# Fotos de campo: PlantDoc

As fotos desta pasta vêm do PlantDoc, publicado sob a licença Creative Commons
Atribuição 4.0 Internacional (CC BY 4.0): https://github.com/pratikkayal/PlantDoc-Dataset

Singh, D.; Jain, N.; Jain, P.; Kayal, P.; Kumawat, S.; Batra, N. PlantDoc: A Dataset
for Visual Plant Disease Detection. CoDS-COMAD 2020.

Usamos só as três pastas de milho com doença:

| Pasta do PlantDoc | Classe aqui |
|---|---|
| Corn Gray leaf spot | cercosporiose |
| Corn leaf blight | helmintosporiose |
| Corn rust leaf | ferrugem_comum |

Alterações feitas por `sojatech_local/scripts/prepare_campo.py`:
- fotos reduzidas para no máximo 512 px no lado maior e regravadas em JPEG;
- fotos repetidas (hash perceptual a até 4 bits de distância) removidas, ficando uma;
- divisão refeita por classe: 50% treino, 15% validação e 35% teste, com semente fixa.

O `manifesto.csv` liga cada arquivo à foto de origem no repositório do PlantDoc (na coluna
`origem`, caracteres que o Windows não aceita em nomes, como `?`, aparecem como `_`).
