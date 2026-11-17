# Roteiro mínimo nos labs

O enunciado pede **uma** destas opções, com a taxa de precisão (*confidence score*):

- **A (principal):** Cloud Vision API (ou um modelo básico no Vertex AI) identificando
  objetos/defeitos em imagens de teste.
- **B (plano B):** Document AI extraindo campos de notas fiscais em PDF.

Fazemos as duas, cada uma no seu lab. Sem bucket, Cloud Function, BigQuery nem pipeline por
evento: `infra/` e o resto deste projeto ficam arquivados.

## Antes de cada lab (Cloud Shell, projeto criado pelo lab)

Repositório privado: use um token só de leitura e revogue depois.

```
gh repo clone AbnerMSaconi/agroflow && cd agroflow && git switch gcp-minimo
cd sojatech_cloud
```

## Lab A: Vision API nas folhas

```
gcloud services enable vision.googleapis.com
pip install google-cloud-vision
export GCP_PROJECT=$(gcloud config get-value project)
python scripts/vision_minimo.py                                    # laboratório: 100 fotos de teste
python scripts/vision_minimo.py --pasta ../data/leaves/campo/teste # campo (PlantDoc)
```

Guardar: `results/vision_test.csv` e `results/vision_teste.csv`, o resumo impresso e prints do
console. O script devolve, por imagem, os 10 rótulos com score, quantas imagens têm algum rótulo
que nomeia praga/doença e o score médio do rótulo top-1.

**O que esperar:** a label detection devolve rótulos genéricos (Leaf, Plant...) com score alto.
Na linha de base local (ResNet-50) 0% das imagens tiveram rótulo de doença. Isso é resultado
para o relatório: o score alto não significa acerto. Se o professor exigir uma taxa de acerto
por classe, o caminho é o Vertex AI AutoML (`infra/vertex_train.sh`, mínimo de 8 horas de nó);
confira antes se o lab permite.

## Lab B: Document AI nas notas

```
gcloud services enable documentai.googleapis.com
pip install google-cloud-documentai
```

No console: **Document AI > Processor gallery > Invoice Parser > Create**, região `us`.
Copiar o **ID** do processador.

```
export GCP_PROJECT=$(gcloud config get-value project)
export DOCAI_PROCESSOR_ID=<id do processador>
python scripts/docai_minimo.py                       # holdout_s9 (avaliar uma vez, veja data/invoices/CONJUNTOS.md)
```

Guardar: `results/docai_holdout_s9.csv`, a tabela impressa e prints do console.

**O que esperar:** o Invoice Parser é treinado em faturas estrangeiras e pode confundir o CNPJ do
emitente com o do destinatário e a data de emissão com a de saída. Isso é resultado, não bug.
Para comparar com o extrator local, use o mesmo `holdout_s9`.
