# Roteiro mínimo nos labs

O enunciado pede **uma** destas opções, com a taxa de precisão (*confidence score*):

- **A (principal):** Cloud Vision API (ou um modelo básico no Vertex AI) identificando
  objetos/defeitos em imagens de teste.
- **B (plano B):** Document AI extraindo campos de notas fiscais em PDF.

Fazemos as duas, cada uma no seu lab. Sem bucket, Cloud Function, BigQuery nem pipeline por
evento: `infra/` e o resto deste projeto ficam arquivados.

## Labs do Skills Boost

| | Lab | Página mostra | Serve para |
|---|---|---|---|
| A | **GSP037** Detect Labels, Faces, and Landmarks in Images with the Cloud Vision API | 10 min, 5 créditos | `vision_minimo.py` |
| B | **GSP1139** Form Parsing with Document AI (Python) | 10 min, 5 créditos | `docai_minimo.py` (com Invoice Parser, veja abaixo) |
| – | GSP1141 Uptraining with Document AI Workbench | 35 min, 5 créditos | **não**: o treino leva horas e não cabe no lab |
| – | OCBL447 Develop an App with the Gemini API | 90 min, 1 crédito | **não**: não usa Vision nem Document AI e não devolve confidence |

Confira o cronômetro assim que iniciar: o tempo é de acesso e não pausa. Com 10 minutos, o
que sobra depois dos passos do próprio lab é pouco; por isso o código vai num zip e os scripts
aceitam uma amostra (`--limite`).

## Antes do lab (na sua máquina)

```
python sojatech_cloud/scripts/empacotar_lab.py     # gera sojatech_cloud/build/agroflow-lab.zip (~9 MB)
```

No Cloud Shell: menu de três pontos > **Upload** > `agroflow-lab.zip`. Depois:

```
python3 -m zipfile -e agroflow-lab.zip . && cd sojatech_cloud
```

(Clonar o repositório privado também funciona, mas autenticar no GitHub gasta tempo do lab.)

## Lab A: Vision API nas folhas (GSP037)

Faça os passos do lab (chave de API, bucket, requisições) e rode:

```
bash scripts/lab_a.sh        # 40 imagens de laboratório e 40 de campo
bash scripts/lab_a.sh 0      # todas: 100 de laboratório e 127 de campo
```

O script habilita a API, instala a biblioteca, roda os dois conjuntos, empacota `results/` em
`resultados_lab_a.zip` e baixa o zip. Guardar `results/vision_test.csv` e
`results/vision_teste.csv`, o resumo impresso e prints do console.

**O que esperar:** a label detection devolve rótulos genéricos (Leaf, Plant...) com score alto. Na
linha de base local (ResNet-50) 0% das imagens tiveram rótulo de doença. Isso é resultado para o
relatório: score alto não é acerto. Se o professor exigir taxa de acerto por classe, o caminho é o
Vertex AI AutoML (`infra/vertex_train.sh`, mínimo de 8 horas de nó); confirme antes se o lab permite.

## Lab B: Document AI nas notas (GSP1139)

O lab cria um **Form Parser**. O `docai_minimo.py` espera o **Invoice Parser** (entidades como
`supplier_tax_id` e `total_amount`). No passo de criar o processador, crie também um
**Invoice Parser** (Document AI > Explore processors > Specialized) e use o ID dele. Não verifiquei
se o projeto do lab deixa criar processadores especializados; se não deixar, o Form Parser devolve
pares chave/valor e precisaria de outro extrator.

```
bash scripts/lab_b.sh <ID_DO_INVOICE_PARSER> [REGIAO]     # REGIAO padrão: us
```

O script faz um teste rápido em 3 notas da `validacao_s8` (acha erro de ID, região ou permissão
sem gastar o holdout), pergunta se pode seguir e roda o `holdout_s9` inteiro, **uma vez**
(veja `data/invoices/CONJUNTOS.md`). Depois empacota `results/` em `resultados_lab_b.zip` e baixa.
Guardar também a tabela impressa e prints do console.

**O que esperar:** o Invoice Parser é treinado em faturas estrangeiras e pode confundir o CNPJ do
emitente com o do destinatário e a data de emissão com a de saída. Isso é resultado, não bug.
