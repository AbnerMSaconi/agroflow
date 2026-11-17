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

Faça os passos do lab (chave de API, bucket, requisições) e, com a API habilitada:

```
gcloud services enable vision.googleapis.com
pip install google-cloud-vision
python scripts/vision_minimo.py --limite 40                         # laboratório, amostra de 40
python scripts/vision_minimo.py --pasta ../data/leaves/campo/teste --limite 40
```

Sem `--limite` são 100 fotos de laboratório e 127 de campo. Guardar `results/vision_test.csv` e
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
gcloud services enable documentai.googleapis.com
pip install google-cloud-documentai
export GCP_PROJECT=$(gcloud config get-value project)
export DOCAI_PROCESSOR_ID=<id do Invoice Parser>
python scripts/docai_minimo.py --limite 20      # holdout_s9: avaliar uma vez (veja data/invoices/CONJUNTOS.md)
```

Se for rodar as 40 notas, tire o `--limite`. Guardar `results/docai_holdout_s9.csv`, a tabela
impressa e prints. Amostra e conjunto completo não se misturam: o número do relatório vem de uma
única execução.

**O que esperar:** o Invoice Parser é treinado em faturas estrangeiras e pode confundir o CNPJ do
emitente com o do destinatário e a data de emissão com a de saída. Isso é resultado, não bug.
