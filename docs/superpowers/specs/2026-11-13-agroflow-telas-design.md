# AgroFlow: telas prod e press

Desenho, 13/11/2026. Situação: aguardando aprovação.

## Intenção

Hoje o `sojatech_local` só roda pelo terminal. A interface precisa **entregar o produto**,
ou seja, os passos 3 a 6 do fluxo: entrada, roteamento, extração ou classificação, e
gravação. Ela serve para usar o sistema sem terminal e para ser o diferencial da
apresentação do Workshop P2. A avaliação e o relatório ficam fora da interface: quem
apresenta mostra o relatório à parte.

São duas páginas sobre o mesmo fluxo:

- **prod**: para operar no dia a dia, por quem recebe as notas e as fotos de folhas na SojaTech.
- **press**: para projetar na apresentação. A banca vê cada arquivo andar pelo fluxo.

## Objetivos

- Processar notas (PDF) e folhas (JPG/PNG) soltas na página ou copiadas para
  `bucket/entrada/`, sem travar a tela.
- Mostrar cada arquivo passando por: chegou → processando → aceito, conferir ou rejeitado.
- Decidir entre aceito e conferir pelo limiar de confiança que a avaliação calculou. É a
  tese do trabalho (confiança não é acerto) virando regra de operação.
- No detalhe da nota: a DANFE com cada campo marcado onde foi achado, o valor e a
  confiança de cada campo, e o campo não encontrado em destaque.
- No detalhe da folha: a imagem, a doença, a confiança comparada ao limiar, as
  probabilidades das 4 classes e os rótulos genéricos da linha de base.
- prod e press ao vivo e iguais entre si: um arquivo que entra por qualquer caminho
  aparece nas duas.
- Rodar na máquina (Windows, com ou sem GPU) e no Google Colab.

## Não objetivos

- Corrigir ou confirmar valores na tela. A situação "conferir" só aponta o problema.
- Treinar, gerar dados, avaliar ou mostrar métricas na interface.
- GCP, login, vários usuários, layout de celular, instalador.

## Antiobjetivos (falha mesmo que funcione)

- A press travar, piscar ou mostrar estado velho durante a demo.
- Depender de internet na hora da apresentação. Fontes e scripts ficam no repositório.
- Contaminar a avaliação: arquivos que passam pelas telas não podem entrar nas métricas
  do `evaluate.py`.
- Cara de painel genérico de SaaS.

## Restrições

- Base: `sojatech_local/agroflow` (`pipeline`, `storage` em SQLite, extratores locais).
  Os modelos são RapidOCR, ResNet-50 (linha de base) e EfficientNet-B0
  (`models/leaf_classifier.pt`).
- Tempos medidos: nota com camada de texto ~3 ms, nota escaneada (OCR) ~3 s, folha ~0,1 s.
  A primeira chamada carrega os modelos e leva alguns segundos.
- GPU e OCR processam um arquivo por vez: fila única.
- Windows 11 com Python 3.12 no `.venv` da raiz. O Colab é a alternativa.
- `report/` não muda.

## Abordagens

1. **Web local: FastAPI + HTML/CSS/JS sem etapa de build (escolhida).** Um servidor
   Python roda o fluxo, e `/prod` e `/press` são páginas HTML que consultam uma API.
   - Os esboços aprovados já são HTML.
   - Duas páginas viram dois endereços, e a press vai em tela cheia no projetor.
   - A animação da esteira é natural no navegador.
   - Roda local e no Colab.
   - O agy pode construir a press contra uma API documentada, sem tocar no Python.
   - Custo: duas linguagens e um servidor local.
2. **PySide6 (desktop), duas janelas no mesmo processo.** Descartada:
   - não roda no Colab;
   - animação e acabamento visual dão mais trabalho em Qt;
   - os esboços não se aproveitam;
   - a divisão com o agy fica mais acoplada.
3. **Frameworks Python de interface (Gradio, Streamlit, NiceGUI).** Descartada: a esteira
   ao vivo e as caixas sobre a DANFE brigam com o modelo desses frameworks, e o resultado
   fica com cara de demo de framework.

O usuário entregou a escolha técnica ("pode começar"). A escolha da abordagem 1 é minha.

## O que o usuário decidiu

- A interface cobre os passos 3 a 6. Avaliação e relatório ficam de fora.
- prod e press são páginas separadas sobre o mesmo fluxo.
- prod no formato "caixa de entrada" (esboço A); press no formato "esteira" (esboço C).
- O agy constrói a parte mais simples (a press). Eu fico com a mais complexa e reviso o
  trabalho do agy.

## Desenho

### Visão geral

```
navegador /prod e /press ──(consulta a cada 0,5 s)──► servidor FastAPI
                                                         │ POST /api/enviar grava em bucket/entrada/
bucket/entrada/ ──(watchdog)──► fila ──► 1 thread ──► pipeline existente
                                                         │
                          itens + resultados (SQLite)  ◄─┤
                          mídia em results/fluxo/<id>/ ◄─┘
```

### Motor do fluxo (`agroflow/fluxo.py`, novo)

- Um único `Fluxo` por processo, com observador de pasta (watchdog), fila, uma thread
  que processa e o registro dos itens.
- **Toda entrada passa pela pasta.**
  - PDF vai para `bucket/entrada/notas/`, imagem para `bucket/entrada/imagens/` e
    qualquer outra extensão para a raiz de `bucket/entrada/`.
  - O upload e "Enviar exemplos" gravam com um nome temporário começando por `.` e
    depois renomeiam. O observador ignora nomes com `.` e trata os eventos de criação e
    de renomeação (`created` e `moved`, usando o destino).
  - Cópia manual (Explorer) não tem como renomear: o motor espera o tamanho do arquivo
    ficar estável por 0,5 s antes de enfileirar.
  - Assim prod, press, o `watch_bucket.py` e a cópia manual seguem o mesmo caminho.
- Arquivo detectado vira um item `chegou` e entra na fila. Um evento repetido do mesmo
  caminho é ignorado enquanto o item estiver pendente.
- A thread então:
  1. marca o item como `processando` e chama o pipeline;
  2. decide a situação;
  3. salva a mídia e grava os resultados;
  4. move o arquivo para `processados/` ou para `rejeitados/` com uma linha em
     `rejeitados.log`, como hoje. Se o nome já existir no destino, acrescenta `_<id>`;
  5. marca o estado final.
- **Aquecimento:** ao iniciar, a thread carrega o OCR e os dois modelos antes de
  processar qualquer arquivo. A API informa `modelos: "carregando" | "prontos" | "faltando"`.
  "faltando" quer dizer que `models/leaf_classifier.pt` não existe, o que acontece num
  Colab novo. Nesse caso as páginas mostram o comando para treinar e as folhas são
  rejeitadas com esse motivo. As notas continuam funcionando.
- Ao iniciar, processa o que já estiver na entrada. Itens finalizados continuam na tela
  de uma execução para outra, até o "Limpar". Itens não finalizados de uma execução
  anterior são descartados; o arquivo continua na entrada e é redescoberto.
- `scripts/watch_bucket.py` passa a usar o mesmo motor, sem interface.

### Regras de situação

- **rejeitado:** extensão não suportada, arquivo ilegível (`ArquivoInvalido`) ou erro
  inesperado. O motivo diz qual foi.
- **Nota:** aceito se os 4 campos foram achados e cada confiança é ≥ ao limiar das
  notas. Senão, conferir, e o resumo diz quais campos faltaram ou ficaram abaixo.
- **Folha:** aceito se a confiança do classificador é ≥ ao limiar das folhas. Senão,
  conferir.
- **Limiares:** lidos de `results/metricas.json`: `notas_teste.limiar_escolhido` (hoje
  0,05) e `classificador.limiar_escolhido` (hoje 0,90). Se o arquivo não existir, valem
  esses mesmos números.

### Mudanças no código existente

- `invoices/local_extractor.py`: nova `extract_detalhado(path)`, que devolve os campos,
  a fonte, o tamanho da página e a caixa (em pontos) de onde veio cada valor. Quando o
  valor vem da chave de acesso, a caixa é `None`. `extract()` chama a nova função e
  descarta as posições, então nenhum número da avaliação muda.
- `pipeline.py`: nova `processar_detalhado(path, nome)` → `(rows, detalhe)`, com as
  posições, as probabilidades e os rótulos da linha de base. `process_file` passa a
  chamá-la e continua devolvendo só as linhas.
- `storage.py`:
  - nova coluna `origem` em `resultados`: `'lote'` por padrão, `'fluxo'` para o que
    passa pelo motor;
  - migração automática do banco existente com `ALTER TABLE`, e o INSERT passa a nomear
    as colunas;
  - nova tabela `itens`.
- `scripts/evaluate.py`: só considera `origem = 'lote'`.

### Item: contrato da API

```json
{
  "id": 17,
  "arquivo": "nota_005.pdf",
  "tipo": "nota",
  "estado": "conferir",
  "resumo": "valor total não encontrado",
  "motivo": null,
  "recebido_em": "2026-11-13T17:20:01Z",
  "duracao_ms": 3165.4,
  "midia": "/api/midia/17",
  "nota": {
    "fonte": "ocr",
    "campos": [
      {"campo": "cnpj_emitente", "rotulo": "CNPJ do emitente", "valor": "65.167.612/0001-19",
       "exibicao": "65.167.612/0001-19", "confianca": 0.85,
       "caixa": {"x": 63.5, "y": 20.4, "w": 12.7, "h": 1.3}, "situacao": "ok"},
      {"campo": "valor_total", "rotulo": "Valor total", "valor": null, "exibicao": null,
       "confianca": 0.0, "caixa": null, "situacao": "nao_encontrado"}
    ]
  },
  "folha": null
}
```

- `tipo`: `nota | folha | outro`.
- `estado`: `chegou | processando | aceito | conferir | rejeitado`.
- `situacao` de um campo: `ok | baixa | nao_encontrado`.
- `caixa`: em % da página, pronta para posicionar sobre a imagem.
- `exibicao`: o valor já formatado para leitura (`02/09/2026`, `R$ 11.387,59`).
- `midia`: a foto da folha, copiada já na chegada, para a press mostrar a miniatura
  desde a coluna "Chegou". Para nota, é a DANFE renderizada em PNG (110 dpi), disponível
  quando o processamento termina. É `null` enquanto não existe e para itens rejeitados.
- `resumo` também cobre os estados de passagem: "na fila", "lendo a nota",
  "classificando a folha".
- Folha:

```json
"folha": {
  "classe": "helmintosporiose", "rotulo": "Helmintosporiose", "confianca": 0.6546, "limiar": 0.9,
  "probabilidades": [{"classe": "helmintosporiose", "rotulo": "Helmintosporiose", "p": 0.6546}, "..."],
  "linha_de_base": [{"rotulo": "tree frog", "score": 0.0312}, "..."]
}
```

### API

- `GET /` redireciona para `/prod`. `GET /prod` e `GET /press` entregam as páginas.
  `/static/...` serve os arquivos das páginas.
- `GET /api/estado?desde=<versao>` → `{versao, completo, modelos, limiares, ocioso, itens}`.
  - Sem `desde`, ou se houve uma limpeza depois dessa versão: devolve a lista completa
    (`completo: true`) e o cliente troca tudo.
  - Com `desde`: devolve só os itens alterados depois dessa versão (`completo: false`).
  - `ocioso`: não há item em `chegou` nem em `processando`.
  - A lista traz no máximo os 200 itens mais recentes.
- `POST /api/enviar` (multipart, vários arquivos, até 25 MB cada) → grava na entrada e
  responde `{recebidos: n}`. O nome do arquivo é reduzido ao nome base.
- `POST /api/exemplos` → copia a amostra para a entrada, um arquivo a cada ~0,8 s, em
  segundo plano. Responde na hora. Pode ser chamado de novo antes de terminar: só
  acrescenta mais arquivos.
- `POST /api/limpar` → só funciona com o fluxo ocioso; senão responde 409. Apaga os
  itens, os resultados de origem `'fluxo'` e a mídia. Não mexe nos arquivos já movidos
  nem nos resultados de lote.
- `GET /api/midia/<id>` → a imagem do item.
- Consulta a cada 500 ms, em vez de WebSocket ou SSE, porque funciona igual local e
  atrás do proxy do Colab.

### Amostra de "Enviar exemplos"

Lista fixa no código, montada para a demo ter todos os desfechos, com notas e folhas
intercaladas:

| Arquivo | Origem | Resultado esperado |
|---|---|---|
| nota_002.pdf | teste, digital | aceito |
| nota_006.pdf | teste, escaneada | aceito |
| nota_001.pdf | teste, layout novo | conferir (valor total não encontrado) |
| nota_005.pdf | teste, layout novo, escaneada | conferir |
| ferrugem_comum_000.jpg | teste | aceito (99%) |
| saudavel_000.jpg | teste | aceito (99,6%) |
| helmintosporiose_000.jpg | teste | aceito (97,6%) |
| cercosporiose_000.jpg | teste | aceito (99,6%) |
| cercosporiose_012.jpg | teste | conferir (erro real: disse helmintosporiose, 65%) |
| ferrugem_comum_001.jpg | teste | conferir (certa, mas 84%) |
| anotacoes.txt | gerado na hora | rejeitado |

São cerca de 20 s de processamento.

### Páginas

**Comum** (eu faço; as duas páginas usam):
- `tokens.css`: cores, tipos e espaçamentos.
- `api.js`: consulta e estado local.
- `detalhe.js`: desenha o detalhe de um item dentro de um contêiner. Cobre nota, folha
  e rejeitado.

**prod** (eu faço):
- Cabeçalho com a área de soltar arquivos, o estado do observador e o dos modelos.
- Filtros por situação, com contagem.
- Lista com o mais novo em cima: nome, resumo, situação e tempo.
- Detalhe ao lado, pelo `detalhe.js`.
- Seleção pelo teclado com ↑ e ↓.

**press** (o agy faz):
- Cabeçalho com o nome, uma linha de explicação e os botões "Enviar exemplos" e
  "Limpar". O "Limpar" fica desabilitado se o fluxo não estiver ocioso.
- Esteira com 5 colunas (Chegou, Processando, Aceito, Conferir, Rejeitado) e contagens
  grandes.
- Cartões com miniatura (foto da folha, ícone de PDF ou ícone com a extensão), nome
  curto e resumo.
- Ordem: em "Chegou", a ordem da fila (o próximo em cima). Nas colunas finais, o mais
  recente em cima.
- O cartão anima ao mudar de coluna, respeitando `prefers-reduced-motion`.
- Clicar num cartão abre um painel lateral com o `detalhe.js`.
- Aceita arquivos soltos em qualquer ponto da página, sem área de soltar visível. Uma
  camada aparece só enquanto o arquivo está sendo arrastado.
- Tipografia para projetor: corpo ≥ 16 px. Cabe em 1366×768 e em 1920×1080, e as colunas
  rolam por dentro.

**Detalhe:**
- **Nota:** a imagem da DANFE com uma caixa em cada campo achado (verde, ou âmbar se
  ficou abaixo do limiar). Ao lado, a lista de campos com valor e confiança, com o campo
  não encontrado em destaque. Embaixo, a fonte (texto ou OCR) e o tempo.
- **Folha:** barras horizontais das 4 classes, com rótulo e porcentagem escritos, e a
  classe prevista destacada. Uma linha vertical no limiar (90%) mostra por que a folha
  foi para conferir. Embaixo, os rótulos da linha de base.

**Regras gerais:**
- A situação nunca aparece só por cor: sempre ícone e palavra (✓ aceito, ! conferir,
  ✕ rejeitado).
- Nada externo em tempo de execução: as fontes ficam em `static/fonts/`.

### Identidade visual

Escolhida pelo usuário entre duas direções (esboço `visual-style`). Os tokens ficam no
`tokens.css`, usado pelas duas páginas.

### Como rodar

- **Local:** `python scripts/app.py` sobe em http://127.0.0.1:8000, abre a /prod no
  navegador e mostra o link da /press. Opções: `--porta` e `--sem-navegador`.
- **Colab:** uma seção nova no notebook do `sojatech_local` sobe o servidor em segundo
  plano e abre /prod e /press pelo proxy do Colab
  (`google.colab.output.serve_kernel_port_as_window`).
- **Dependências novas:** `fastapi`, `uvicorn`, `python-multipart`. Para os testes:
  `pytest` e `httpx`.
- `results/fluxo/` fica fora do Git.

### Testes

- Regras de situação: teste unitário.
- `extract_detalhado`:
  - valores iguais aos de `extract()` em 6 notas (digitais, escaneadas e layout novo);
  - caixas dentro da página.
- Motor:
  - nota, folha e `.txt` passam pelos estados certos;
  - um evento duplicado não cria item duplicado;
  - `limpar` zera os itens e a mídia.
- API, com `TestClient`: estado completo e incremental, upload, exemplos, limpar, mídia
  e o 409 do limpar.
- `evaluate.py` dá os mesmos números com itens de fluxo no banco.
- Páginas: conferência manual e captura de tela headless em 1366×768 e 1920×1080.

### Divisão do trabalho

- **Eu:**
  - o motor e as mudanças no código existente;
  - a API, o `tokens.css`, o `api.js` e o `detalhe.js`;
  - a prod e a seção do Colab;
  - os testes, a integração e a revisão.
- **agy (Antigravity CLI, modo não interativo):** `press.html`, `press.css` e
  `press.js`, seguindo este documento, o contrato da API e os tokens. Ele só toca nesses
  três arquivos e testa contra o servidor real rodando nesta máquina. Eu reviso antes de
  juntar.

### Decisões minhas para conferir

Lacunas encontradas ao reler o documento como quem vai construir, decididas por mim:

1. Arquivo que não é PDF nem imagem entra pela raiz de `bucket/entrada/`.
2. Upload e exemplos gravam com nome temporário e renomeiam; cópia manual espera o
   tamanho estabilizar. Sem isso, o motor leria PDFs pela metade.
3. A foto da folha aparece na press desde "Chegou"; a DANFE só depois de processada.
4. Sem `leaf_classifier.pt` (Colab novo), as telas avisam como treinar e as notas
   seguem funcionando.
5. Itens finalizados sobrevivem a reiniciar o servidor, até o "Limpar".
6. Na press, "Chegou" fica em ordem de fila e as colunas finais com o mais recente em
   cima.
7. A press aceita arquivos soltos em qualquer ponto da página, sem área visível.
8. "Enviar exemplos" pode ser clicado de novo durante uma rodada.

### Fica a critério de quem constrói

- Nomes internos e organização das funções.
- Detalhes de CSS dentro da direção visual escolhida.
- Texto exato dos resumos, desde que diga o que aconteceu, em português simples.
