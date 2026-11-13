# Classificador de folhas para laboratório e campo: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** trocar o classificador de folhas por uma rede maior, escolhida numa disputa justa.
Treinar uma versão só com laboratório e outra com laboratório + campo, e medir as duas num teste de
laboratório e num teste de campo novo.

**Arquitetura:**
- As partições de dados ficam em manifestos fixos: `data/leaves/manifesto_lab.csv` e
  `data/leaves/campo/manifesto.csv`.
- Três módulos novos em `agroflow/leaves/`:
  - `conjuntos`, sem torch: manifestos, hash e divisão;
  - `redes`: construção e pré-processamento;
  - `treino`.
- Os scripts são finos e chamam esses módulos.
- `run_batch` e `evaluate` passam a nomear e a avaliar cada foto por conjunto e partição.

**Tecnologia:** Python 3.12, torch 2.11 + torchvision 0.26 (cu128), Pillow, pandas, scikit-learn.
`pytest` é novo e só de desenvolvimento.

**Desenho:** `docs/superpowers/specs/2026-11-13-modelo-folhas-design.md`

Todos os comandos rodam a partir de `sojatech_local/`, com `PY=../.venv/Scripts/python`.

## Restrições globais

**Dados**
- O teste de laboratório é o mesmo de hoje: as 25 fotos por classe de `data/leaves/test`, idênticas
  byte a byte.
- Nenhuma escolha (rede, época ou limiar) usa a partição `teste`.
- **Laboratório:** 450 fotos de treino por classe, validação fixa de `round(0.15 · n)` delas,
  semente 42.
- **Campo:**
  - classes: `Corn Gray leaf spot` → `cercosporiose`, `Corn leaf blight` → `helmintosporiose`,
    `Corn rust leaf` → `ferrugem_comum`;
  - fotos repetidas: dHash de 64 bits, e distância ≤ 4 conta como repetida;
  - divisão por classe: `round(0.5 · n)` treino, `round(0.15 · n)` validação e o resto teste,
    semente 42;
  - saída em JPEG com o lado maior ≤ 512 px.
- O PlantDoc é CC BY 4.0: `data/leaves/campo/FONTE.md` traz a atribuição.

**Redes e treino**
- Só redes do torchvision: `efficientnet_b0`, `efficientnet_v2_s`, `convnext_small` e `vit_b_16`
  (pesos `IMAGENET1K_SWAG_E2E_V1`, 384 px). Nenhuma biblioteca nova além do `pytest`.
- Na mistura, as fotos de campo são ≈ 1/3 das amostras de cada época (amostragem ponderada).
- **Disputa:**
  - todas com 15 épocas, o mesmo aumento de dados e lote efetivo de 32;
  - vence o maior F1 macro na validação de campo;
  - diferença < 0,02 entre as melhores → vence a de menos parâmetros.
- O modelo `lab` escolhe a época pela validação de laboratório e nunca carrega foto de campo.

**Saídas**
- **Limiar do produto:** o menor limiar com precisão ≥ 0,98 entre os aceitos, calculado na
  validação de campo. Vai para `metricas.json → classificador.limiar_escolhido`.
- **Nomes gravados:** `<lab|campo>/<treino|val|teste>/<classe>/<arquivo>`.
- **Tipos gravados:** `folha_classificador` (produto), `folha_classificador_lab` e `folha_baseline`.
- **Arquivos de modelo:** `models/leaf_classifier.pt` (lab+campo) e
  `models/leaf_classifier_lab.pt`, com as chaves `rede`, `classes`, `resolucao` e `state_dict`, e
  um `.json` ao lado com o `sha256` do arquivo.
- A avaliação das notas fiscais não muda.

## Foco de revisão

1. Foto do PlantDoc em tons de cinza, RGBA, CMYK ou corrompida: vira JPEG RGB ou é pulada com o
   motivo registrado. O script não cai. (Tarefa 3)
2. Nomes com espaço, parênteses ou extensão maiúscula (`Foto (1).JPG`, `.jpeg`, `.png`): todos são
   lidos, e a saída é sempre `<classe>_campo_NNN.jpg`. (Tarefa 3)
3. Rodar `prepare_campo` ou `prepare_leaves` de novo dá os mesmos arquivos e o mesmo manifesto, e
   preparar o laboratório não apaga o campo. (Tarefas 2 e 3)
4. O arquivo de modelo antigo, sem a chave `rede`, carrega como EfficientNet-B0 a 224 px. (Tarefa 6)
5. O teste de campo não tem `saudavel`, mas o modelo pode prever `saudavel`: as métricas usam as 3
   classes de campo, `saudavel` conta como erro e aparece na matriz, e nada quebra (hoje o
   `rep["accuracy"]` daria `KeyError`). (Tarefa 8)

---

### Task 0: branch e infraestrutura de testes

**Arquivos:**
- Criar: `sojatech_local/requirements-dev.txt` (uma linha: `pytest`)
- Criar: `sojatech_local/tests/conftest.py`

- [ ] **Passo 1:** `git switch -c modelo-folhas`. Commitar os dois desenhos e este plano.
- [ ] **Passo 2:** `$PY -m pip install -r requirements-dev.txt`.
- [ ] **Passo 3:** Escrever o `conftest.py`:
  - põe `sojatech_local/` e `sojatech_local/scripts/` no `sys.path`;
  - fornece a fixture `fazer_imagem`, uma função
    `fazer_imagem(caminho: Path, semente: int, tamanho=(64, 64), modo="RGB") -> Path`. Ela grava um
    padrão suave e determinístico (ruído RGB 8×8 do numpy com essa semente, ampliado até `tamanho`
    com BICUBIC), convertido para `modo`, no formato dado pela extensão. Ruído puro não serve: o
    dHash dele muda com a recompressão.
- [ ] **Passo 4:** `$PY -m pytest tests -q` → "no tests ran".
- [ ] **Passo 5:** Commit.

### Task 1: conjuntos (manifestos, hash e divisão, sem torch)

**Arquivos:**
- Criar: `agroflow/leaves/conjuntos.py`
- Modificar: `agroflow/config.py`. Acrescentar:
  - `CAMPO_DIR = LEAVES_DIR / "campo"`
  - `MANIFESTO_LAB = LEAVES_DIR / "manifesto_lab.csv"`
  - `MANIFESTO_CAMPO = CAMPO_DIR / "manifesto.csv"`
  - `LEAF_MODEL_LAB = MODELS / "leaf_classifier_lab.pt"`
  - `DISPUTA = RESULTS / "disputa_redes.json"`
- Teste: `tests/test_conjuntos.py`

**Interfaces que esta tarefa fornece:**
- `CLASSES = ["cercosporiose", "ferrugem_comum", "helmintosporiose", "saudavel"]`
- `PASTAS_PLANTDOC = {"Corn Gray leaf spot": "cercosporiose", "Corn leaf blight": "helmintosporiose",
  "Corn rust leaf": "ferrugem_comum"}`
- `@dataclass(frozen=True) class Item: arquivo: Path; classe: str; conjunto: str; particao: str`
- `dhash(img: Image.Image) -> int` e `distancia(a: int, b: int) -> int`
- `indices_unicos(hashes: list[int], limite: int = 4) -> list[int]`: percorre na ordem de entrada e
  mantém um hash só se ele estiver a mais de `limite` bits de todos os já mantidos. Devolve os
  índices mantidos.
- `dividir_estratificado(chaves: list[tuple[str, str]], seed: int = 42, fracoes=(0.5, 0.15)) -> dict[str, str]`:
  recebe pares `(id, classe)` e devolve `id → "treino" | "val" | "teste"`.
- `escrever_manifesto(caminho: Path, linhas: list[dict]) -> None`: CSV UTF-8, colunas na ordem das
  chaves da primeira linha, linhas ordenadas por `arquivo`, fim de linha `\n`.
- `itens(conjunto: str, particao: str) -> list[Item]`:
  - lê `config.MANIFESTO_LAB` (base `config.LEAVES_DIR`) ou `config.MANIFESTO_CAMPO`
    (base `config.CAMPO_DIR`);
  - lê os caminhos do `config` na hora da chamada, para os testes poderem trocá-los.
- `nome_folha(item: Item) -> str` e `ler_nome_folha(nome: str) -> tuple[str, str, str] | None`.

- [ ] **Passo 1: escrever os testes que falham**

```python
def test_dhash_quase_igual_para_copia_recomprimida(tmp_path, fazer_imagem):
    a = Image.open(fazer_imagem(tmp_path / "a.png", 1, (200, 150)))
    a.convert("RGB").save(tmp_path / "b.jpg", quality=60)
    assert distancia(dhash(a), dhash(Image.open(tmp_path / "b.jpg"))) <= 4

def test_dhash_distante_para_fotos_diferentes(tmp_path, fazer_imagem):
    a, b = (Image.open(fazer_imagem(tmp_path / f"{s}.png", s, (200, 150))) for s in (1, 2))
    assert distancia(dhash(a), dhash(b)) > 4

def test_indices_unicos_mantem_o_primeiro():
    assert indices_unicos([0b0, 0b1, 2**64 - 1, 0b11]) == [0, 2]

def test_divisao_estratificada():
    chaves = [(f"a{i:03d}", "cercosporiose") for i in range(68)] + [(f"b{i:03d}", "helmintosporiose") for i in range(192)]
    d = dividir_estratificado(chaves)
    conta = lambda c, p: sum(1 for k, cl in chaves if cl == c and d[k] == p)
    assert [conta("cercosporiose", p) for p in ("treino", "val", "teste")] == [34, 10, 24]
    assert [conta("helmintosporiose", p) for p in ("treino", "val", "teste")] == [96, 29, 67]
    assert dividir_estratificado(chaves) == d and dividir_estratificado(chaves, seed=7) != d

def test_nome_folha_ida_e_volta():
    item = Item(Path("x/ferrugem_comum_campo_001.jpg"), "ferrugem_comum", "campo", "teste")
    assert nome_folha(item) == "campo/teste/ferrugem_comum/ferrugem_comum_campo_001.jpg"
    assert ler_nome_folha(nome_folha(item)) == ("campo", "teste", "ferrugem_comum")
    assert ler_nome_folha("demo_folha.jpg") is None and ler_nome_folha("cercosporiose/x.jpg") is None
```

- [ ] **Passo 2:** `$PY -m pytest tests/test_conjuntos.py -q` → falha com `ImportError`.
- [ ] **Passo 3:** Implementar.
  - **dHash:** converter para tons de cinza, reduzir para 9×8 com LANCZOS e, em cada linha,
    gerar o bit 1 quando o pixel da esquerda é menor que o da direita (64 bits).
  - **Divisão por classe:** ordenar os ids da classe, embaralhar com
    `random.Random(f"{seed}-{classe}")` (um gerador por classe, para a divisão de uma classe não
    depender das outras) e cortar `round(f0·n)` para treino, `round(f1·n)` para validação e o resto
    para teste.
- [ ] **Passo 4:** `$PY -m pytest tests/test_conjuntos.py -q` → passa.
- [ ] **Passo 5:** Commit.

### Task 2: `prepare_leaves` com 450 fotos por classe e validação fixa

**Arquivos:**
- Modificar: `scripts/prepare_leaves.py`. O `main()` passa a chamar `preparar_lab`.
- Teste: `tests/test_prepare_leaves.py`

**Interfaces:**
- Usa: `CLASSES` e `escrever_manifesto` (Tarefa 1).
- Fornece:
  `preparar_lab(origem: Path, destino: Path, treino: int = 450, teste: int = 25, frac_val: float = 0.15, seed: int = 42) -> None`.
  Escreve `destino/"manifesto_lab.csv"` com as colunas `arquivo` (relativo a `destino`, separado
  por `/`), `classe` e `particao`.

**Para o teste de hoje continuar idêntico:**
- Manter o sorteio exato de hoje (`scripts/prepare_leaves.py:38-49`): um único
  `random.Random(seed)`, que embaralha `sorted(glob("*.[jJ][pP][gG]"))` de cada pasta na ordem do
  dicionário `CLASSES` do script; teste = `imgs[:teste]`, treino = `imgs[teste:teste + treino]`,
  nomes `f"{classe}_{i:03d}.jpg"` numerados a partir de 000 em cada partição.
- As fotos de validação saem de um gerador separado, `random.Random(f"{seed}-val-{classe}")`,
  que embaralha os nomes de treino da classe. As primeiras `round(frac_val · treino)` são validação.
- Apagar só `destino/"train"`, `destino/"test"` e o manifesto. Nunca tocar em `destino/"campo"`.

- [ ] **Passo 1: escrever os testes que falham.** O `origem` falso tem as 4 pastas do PlantVillage
  com 40 fotos cada, criadas por `fazer_imagem`.

```python
def test_teste_e_inicio_do_treino_estaveis(tmp_path, origem_falsa):
    preparar_lab(origem_falsa, tmp_path / "d1", treino=10, teste=5)
    preparar_lab(origem_falsa, tmp_path / "d2", treino=20, teste=5)
    assert arquivos_e_bytes(tmp_path / "d1/test") == arquivos_e_bytes(tmp_path / "d2/test")
    assert arquivos_e_bytes(tmp_path / "d1/train").items() <= arquivos_e_bytes(tmp_path / "d2/train").items()

def test_validacao_fixa_no_manifesto(tmp_path, origem_falsa):
    for _ in range(2):
        preparar_lab(origem_falsa, tmp_path / "d", treino=20, teste=5)
        texto = (tmp_path / "d/manifesto_lab.csv").read_text(encoding="utf-8")
    m = pd.read_csv(tmp_path / "d/manifesto_lab.csv")
    assert (m[m.particao == "val"].groupby("classe").size() == 3).all()
    assert set(m.particao) == {"treino", "val", "teste"} and texto == (tmp_path / "d/manifesto_lab.csv").read_text(encoding="utf-8")

def test_nao_apaga_campo(tmp_path, origem_falsa):
    (tmp_path / "d/campo").mkdir(parents=True); (tmp_path / "d/campo/x.txt").write_text("fica")
    preparar_lab(origem_falsa, tmp_path / "d", treino=10, teste=5)
    assert (tmp_path / "d/campo/x.txt").exists()
```

  `arquivos_e_bytes(pasta) -> dict[str, bytes]` é uma função auxiliar do próprio teste.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 3: `prepare_campo`

**Arquivos:**
- Criar: `scripts/prepare_campo.py`
- Teste: `tests/test_prepare_campo.py`

**Interfaces:**
- Usa: `dhash`, `indices_unicos`, `dividir_estratificado`, `escrever_manifesto` e `PASTAS_PLANTDOC`.
- Fornece: `baixar_plantdoc(destino: Path) -> Path`.
  - Se as 6 pastas (`train/` e `test/` das 3 classes) já existem em `destino`, só devolve o caminho.
  - Senão, faz `git clone --filter=blob:none --no-checkout --depth 1
    https://github.com/pratikkayal/PlantDoc-Dataset <destino>`, depois
    `git sparse-checkout set --no-cone` com as 6 pastas, e por fim `git checkout`.
- Fornece:
  `preparar_campo(origem: Path, destino: Path, seed: int = 42, lado_max: int = 512, limite: int = 4) -> dict`,
  que devolve `{"lidas": int, "puladas": list[tuple[str, str]], "repetidas": int,
  "por_particao": {particao: {classe: int}}}`. `lidas` conta todos os arquivos de imagem
  encontrados, então `lidas - len(puladas) - repetidas` = fotos gravadas.

**Comportamento:**
- **Leitura:** lê `.jpg`, `.jpeg` e `.png` sem diferenciar maiúsculas, em ordem de caminho. Cada foto
  passa por `ImageOps.exif_transpose(...).convert("RGB")` e `thumbnail((lado_max, lado_max))`. Só a
  miniatura fica na memória (as originais chegam a vários MB cada). Se der erro, a foto entra em
  `puladas` com a mensagem.
- **Repetidas:** dHash das miniaturas e `indices_unicos` sobre todas as fotos juntas. A primeira
  ocorrência fica.
- **Divisão:** `dividir_estratificado` com o id = caminho relativo à origem.
- **Gravação:**
  - em `destino/<particao>/<classe>/<classe>_campo_NNN.jpg`, com NNN numerando a classe a partir de
    000, em ordem de origem;
  - JPEG com qualidade 90;
  - antes de gravar, apaga `treino/`, `val/`, `teste/` e o manifesto.
- **Manifesto:** colunas `arquivo` (relativo), `classe`, `particao`, `origem` (relativo, com `/`)
  e `dhash` (16 dígitos hex).
- **`FONTE.md`:** texto fixo. Diz que as fotos vêm do PlantDoc (Singh et al., 2020), licença
  CC BY 4.0, com o link do repositório. Diz também o que foi alterado: fotos reduzidas, repetidas
  removidas, divisão refeita.
- **`main()`:**
  `baixar_plantdoc(config.DOWNLOADS / "PlantDoc")` → `preparar_campo(..., config.CAMPO_DIR)` →
  imprime o resumo.

- [ ] **Passo 1: escrever os testes que falham.** A fixture monta um PlantDoc falso com:
  - `train/Corn rust leaf/`: `a.jpg`, `Foto (1).JPG`, `g.png` (modo L), `r.png` (RGBA) e
    `grande.jpg` (1200×800);
  - `test/Corn rust leaf/a_copia.jpg`: a `a.jpg` regravada com qualidade 60;
  - `train/Corn leaf blight/`: `c.jpeg` (CMYK) e `quebrada.jpg` (bytes truncados);
  - mais 10 fotos distintas por classe.

```python
def test_prepara_campo(tmp_path, plantdoc_falso):
    res = preparar_campo(plantdoc_falso, tmp_path / "campo")
    assert any(a.endswith("quebrada.jpg") for a, _ in res["puladas"]) and res["repetidas"] == 1
    saidas = sorted((tmp_path / "campo").glob("*/*/*.jpg"))
    for f in saidas:
        with Image.open(f) as im:
            assert im.mode == "RGB" and max(im.size) <= 512
        assert re.fullmatch(r"(cercosporiose|ferrugem_comum|helmintosporiose)_campo_\d{3}\.jpg", f.name)
    m = pd.read_csv(tmp_path / "campo/manifesto.csv", dtype=str)
    assert len(m) == len(saidas) == res["lidas"] - len(res["puladas"]) - res["repetidas"]
    hashes = [int(h, 16) for h in m.dhash]
    assert all(distancia(a, b) > 4 for a, b in itertools.combinations(hashes, 2))

def test_prepara_campo_idempotente(tmp_path, plantdoc_falso):
    preparar_campo(plantdoc_falso, tmp_path / "c"); antes = (tmp_path / "c/manifesto.csv").read_bytes()
    preparar_campo(plantdoc_falso, tmp_path / "c")
    assert (tmp_path / "c/manifesto.csv").read_bytes() == antes

def test_fonte_tem_atribuicao(tmp_path, plantdoc_falso):
    preparar_campo(plantdoc_falso, tmp_path / "c")
    texto = (tmp_path / "c/FONTE.md").read_text(encoding="utf-8")
    assert "PlantDoc" in texto and "CC BY 4.0" in texto
```

- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 4: redes

**Arquivos:**
- Criar: `agroflow/leaves/redes.py`
- Teste: `tests/test_redes.py`

**Interfaces que esta tarefa fornece:**
- `REDES: dict[str, dict]`, com as chaves `pesos` (enum de pesos do torchvision) e `lote` (micro-lote
  que cabe em 8 GB):

| Rede | Pesos | Lote |
|---|---|---|
| `efficientnet_b0` | `EfficientNet_B0_Weights.IMAGENET1K_V1` | 32 |
| `efficientnet_v2_s` | `EfficientNet_V2_S_Weights.IMAGENET1K_V1` | 16 |
| `convnext_small` | `ConvNeXt_Small_Weights.IMAGENET1K_V1` | 32 |
| `vit_b_16` | `ViT_B_16_Weights.IMAGENET1K_SWAG_E2E_V1` | 8 |

- `REDE_PADRAO = "efficientnet_b0"`. A Tarefa 10 troca pela vencedora.
- `resolucao(nome: str) -> int`: `pesos.transforms().crop_size[0]`.
- `n_parametros(nome: str) -> int`: `pesos.meta["num_params"]`.
- `construir_rede(nome: str, n_classes: int, pretreinada: bool = True) -> nn.Module`:
  - troca a última camada: `classifier[1]` (EfficientNets), `classifier[2]` (ConvNeXt) ou
    `heads.head` (ViT);
  - com `pretreinada=False`, constrói com `weights=None`. A ViT precisa de `image_size=384`.
- `transformacoes(nome: str, treino: bool) -> Callable[[Image.Image], Tensor]`:
  - **avaliação:** `pesos.transforms()`;
  - **treino:** `RandomResizedCrop(res, scale=(0.6, 1))`, espelhamentos horizontal e vertical,
    `TrivialAugmentWide`, `ColorJitter(0.2, 0.2, 0.2)`, `RandomApply([GaussianBlur(5)], p=0.2)`,
    `ToTensor`, `Normalize` com a média e o desvio de `pesos.transforms()`, e
    `RandomErasing(p=0.25)`.

- [ ] **Passo 1: escrever os testes que falham**

```python
PARES = [("efficientnet_b0", 224), ("efficientnet_v2_s", 384), ("convnext_small", 224), ("vit_b_16", 384)]

@pytest.mark.parametrize("nome,res", PARES)
def test_rede_sem_pesos_da_4_saidas(nome, res):
    m = construir_rede(nome, 4, pretreinada=False).eval()
    with torch.no_grad():
        assert m(torch.zeros(1, 3, res, res)).shape == (1, 4)
    assert resolucao(nome) == res

@pytest.mark.parametrize("nome,res", PARES)
def test_transformacoes_no_tamanho_da_rede(nome, res):
    img = Image.new("RGB", (300, 500))
    assert transformacoes(nome, False)(img).shape == transformacoes(nome, True)(img).shape == (3, res, res)

def test_ordem_de_tamanho():
    assert n_parametros("efficientnet_b0") < n_parametros("efficientnet_v2_s") < n_parametros("convnext_small") < n_parametros("vit_b_16")
```

- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 5: treino

**Arquivos:**
- Criar: `agroflow/leaves/treino.py`
- Reescrever: `scripts/train_leaf_classifier.py`
- Modificar: `tests/conftest.py`. Nova fixture
  `manifestos_falsos(tmp_path, monkeypatch, fazer_imagem)`:
  - monta 2 fotos por classe em cada partição de laboratório (4 classes) e de campo (3 classes);
  - escreve os dois manifestos com `escrever_manifesto`;
  - aponta `config.LEAVES_DIR`, `config.CAMPO_DIR`, `config.MANIFESTO_LAB` e
    `config.MANIFESTO_CAMPO` para elas.
- Teste: `tests/test_treino.py`

**Interfaces:**
- Usa: `itens`, `Item` e `CLASSES` (Tarefa 1); `REDES`, `construir_rede`, `transformacoes`,
  `resolucao` e `n_parametros` (Tarefa 4).
- Fornece:
  - `class ImagensDataset(Dataset)`, com `__init__(itens: list[Item], classes: list[str], transform)`;
    o item devolve `(Tensor, int)`.
  - `pesos_amostragem(conjuntos: list[str], fracao_campo: float = 1/3) -> list[float]`. Sem
    `"campo"`, todos os pesos são 1.0. Com campo, o laboratório pesa `(1 - f) / n_lab` e o campo
    pesa `f / n_campo`.
  - `passos_acumulacao(lote_efetivo: int, lote: int) -> int`: `max(1, ceil(lote_efetivo / lote))`.
  - `escolher_vencedora(resultados: list[dict], margem: float = 0.02) -> str`. Recebe dicts com
    `rede`, `f1_val_campo` e `n_parametros`. Entre as redes com F1 a menos de `margem` do melhor
    (diferença < margem), vence a de menos parâmetros.
  - `treinar(rede: str, dados: str, saida: Path, epocas: int = 15, lote: int | None = None,
    lote_efetivo: int = 32, lr: float = 1e-4, seed: int = 42, fracao_campo: float = 1/3,
    pretreinada: bool = True, workers: int = 4, max_por_classe: int | None = None) -> dict`.
    - `lote=None` usa `REDES[rede]["lote"]`.
    - `max_por_classe` corta cada lista (treino e validações) nas primeiras N fotos de cada classe.
      Serve para a rodada rápida da Tarefa 10.
  - `treino.py` importa o módulo (`from agroflow.leaves import conjuntos`) e chama
    `conjuntos.itens(...)`, para o teste poder vigiar as chamadas.

**Como `treinar` funciona:**
- **Dados:** o treino é `itens("lab", "treino")`, mais `itens("campo", "treino")` quando
  `dados == "lab+campo"`. A validação de laboratório sempre roda. A de campo só roda com
  `"lab+campo"`: com `"lab"` nunca se chama `itens("campo", ...)`.
- **Otimização:**
  - AdamW com `weight_decay=0.05`;
  - 1 época de aquecimento linear, depois cosseno;
  - no CUDA: `torch.autocast` + `GradScaler` e `channels_last`;
  - `WeightedRandomSampler(num_samples=len(treino), replacement=True)` com `pesos_amostragem`;
  - acumulação de gradiente com `passos_acumulacao`, com um passo do otimizador também no último
    lote da época (senão, com poucos dados, ele nunca anda);
  - DataLoader com `persistent_workers=True` quando `workers > 0`: no Windows, abrir os processos a
    cada época custa segundos.
- **Época escolhida:** a de maior F1 macro na validação de campo (com `"lab+campo"`) ou de
  laboratório (com `"lab"`). O `state_dict` dessa época fica guardado.
- **Saída:**
  - `saida` recebe `{"rede", "classes", "resolucao", "state_dict"}`;
  - `saida.with_suffix(".json")` recebe `{rede, dados, classes, resolucao, n_parametros, epocas,
    melhor_epoca, lote, passos_acumulacao, val: {"lab": {"acuracia", "f1_macro"}, "campo": {...} | None},
    historico, tempo_treino_s, dispositivo, gpu, sha256}`, e esse mesmo dict é devolvido. O `val`
    traz as métricas da época escolhida.
- **Linha de comando:** `--rede` (padrão `REDE_PADRAO`), `--dados {lab, lab+campo}` (padrão
  `lab+campo`), `--epocas 15`, `--lote` e `--saida`. A saída padrão é `config.LEAF_MODEL` para
  `lab+campo` e `config.LEAF_MODEL_LAB` para `lab`.

- [ ] **Passo 1: escrever os testes que falham**

```python
def test_fracao_de_campo():
    w = pesos_amostragem(["lab"] * 90 + ["campo"] * 10)
    assert abs(sum(w[90:]) / sum(w) - 1 / 3) < 1e-9
    assert set(pesos_amostragem(["lab"] * 5)) == {1.0}

def test_passos_acumulacao():
    assert (passos_acumulacao(32, 8), passos_acumulacao(32, 32), passos_acumulacao(32, 12)) == (4, 1, 3)

def test_empate_vai_para_a_mais_leve():
    r = [dict(rede="vit_b_16", f1_val_campo=0.80, n_parametros=86_000_000),
         dict(rede="convnext_small", f1_val_campo=0.79, n_parametros=50_000_000),
         dict(rede="efficientnet_b0", f1_val_campo=0.70, n_parametros=5_000_000)]
    assert escolher_vencedora(r) == "convnext_small"

def test_treino_relampago_gera_modelo_carregavel(tmp_path, manifestos_falsos):
    info = treinar("efficientnet_b0", "lab+campo", tmp_path / "m.pt", epocas=1, lote=4, pretreinada=False, workers=0)
    ck = torch.load(tmp_path / "m.pt")
    assert (ck["rede"], ck["classes"], ck["resolucao"]) == ("efficientnet_b0", CLASSES, 224)
    assert info["val"]["campo"] is not None
    assert info["sha256"] == hashlib.sha256((tmp_path / "m.pt").read_bytes()).hexdigest()

def test_modelo_lab_nunca_le_campo(tmp_path, manifestos_falsos, monkeypatch):
    original = conjuntos.itens
    def vigiado(conjunto, particao):
        assert conjunto != "campo"
        return original(conjunto, particao)
    monkeypatch.setattr(treino.conjuntos, "itens", vigiado)
    info = treinar("efficientnet_b0", "lab", tmp_path / "m.pt", epocas=1, lote=4, pretreinada=False, workers=0)
    assert info["val"]["campo"] is None
```

- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar `treino.py` e o script.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 6: a inferência lê a rede do arquivo

**Arquivos:**
- Modificar: `agroflow/leaves/local_models.py`
  - sai: `build_classifier` e `classifier_transform`;
  - `_classifier(caminho: str)` com cache por caminho;
  - `classify(path, modelo="produto")`.
- Modificar: `agroflow/leaves/__init__.py`
- Teste: `tests/test_local_models.py`

**Interfaces que esta tarefa fornece:**
- `classify(path, modelo: str = "produto") -> tuple[str, float, dict[str, float]]`. O
  `modelo` `"produto"` lê `config.LEAF_MODEL` e o `"lab"` lê `config.LEAF_MODEL_LAB`.
- Monta a rede com `construir_rede(rede, len(classes), pretreinada=False)` antes do
  `load_state_dict`. Baixar os pesos do ImageNet só para sobrescrevê-los custaria até 330 MB na
  3090. Sem a chave `rede` no arquivo, usa `efficientnet_b0`. O pré-processamento é sempre
  `transformacoes(rede, False)`.
- `classificador_disponivel(modelo: str = "produto") -> bool`: diz se o arquivo existe.
- `modelo_confere() -> bool | None`: compara o `sha256` calculado de `config.LEAF_MODEL` com
  `config.RESULTS / "metricas.json" → modelo_avaliado_sha256`. Devolve `None` se faltar um dos
  dois. As telas usam isso para avisar quando o modelo carregado não é o avaliado.
- As três funções ficam em `local_models.py` e são expostas por `agroflow/leaves/__init__.py`. Os
  testes importam de `agroflow.leaves`.

- [ ] **Passo 1: escrever os testes que falham.** O auxiliar `salvar_ck(caminho, rede, classes,
  com_rede=True)` grava o `state_dict` de `construir_rede(rede, len(classes), False)`.

```python
@pytest.mark.parametrize("rede", ["efficientnet_b0", "efficientnet_v2_s", "convnext_small", "vit_b_16"])
def test_checkpoint_novo(tmp_path, monkeypatch, fazer_imagem, rede):
    salvar_ck(tmp_path / "p.pt", rede, CLASSES); monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "p.pt")
    classe, conf, probs = classify(fazer_imagem(tmp_path / "f.jpg", 3))
    assert classe in CLASSES and 0 <= conf <= 1 and abs(sum(probs.values()) - 1) < 1e-3

def test_checkpoint_antigo_sem_rede(tmp_path, monkeypatch, fazer_imagem):
    salvar_ck(tmp_path / "v.pt", "efficientnet_b0", CLASSES, com_rede=False); monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "v.pt")
    assert classify(fazer_imagem(tmp_path / "f.jpg", 3))[0] in CLASSES

def test_modelo_lab_usa_outro_arquivo(tmp_path, monkeypatch, fazer_imagem):
    salvar_ck(tmp_path / "l.pt", "efficientnet_b0", CLASSES[::-1]); monkeypatch.setattr(config, "LEAF_MODEL_LAB", tmp_path / "l.pt")
    assert list(classify(fazer_imagem(tmp_path / "f.jpg", 3), modelo="lab")[2]) == CLASSES[::-1]

def test_disponivel_e_confere(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "nao.pt")
    assert not classificador_disponivel() and modelo_confere() is None
    (tmp_path / "m.pt").write_bytes(b"pesos"); monkeypatch.setattr(config, "LEAF_MODEL", tmp_path / "m.pt")
    monkeypatch.setattr(config, "RESULTS", tmp_path)
    (tmp_path / "metricas.json").write_text(json.dumps({"modelo_avaliado_sha256": hashlib.sha256(b"pesos").hexdigest()}))
    assert classificador_disponivel() and modelo_confere() is True
    (tmp_path / "m.pt").write_bytes(b"outros")
    assert modelo_confere() is False
```

- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar. Limpar o cache de `_classifier` entre os testes, numa fixture.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 7: pipeline e `run_batch` por conjunto e partição

**Arquivos:**
- Modificar: `agroflow/pipeline.py:31-48`. O `process_leaf` ganha `modelo: str = "produto"`, e o
  tipo gravado passa a ser `"folha_classificador"` ou `"folha_classificador_lab"`.
- Modificar: `scripts/run_batch.py:34-43`
- Teste: `tests/test_folhas_batch.py`

**Interfaces:**
- Usa: `itens` e `nome_folha` (Tarefa 1); `classify(..., modelo)` e `classificador_disponivel(modelo)`
  (Tarefa 6).
- Fornece: `itens_folhas() -> list[Item]` (em `run_batch.py`). Devolve, nesta ordem, lab/val,
  lab/teste, campo/val e campo/teste. Nunca devolve treino.

**`run_batch.py folhas`:**
- limpa só os tipos que vai gerar de novo (hoje já é assim com `--sem-baseline` e
  `--sem-classificador`);
- para cada item, grava com `nome_folha(item)`;
- roda a linha de base só nas partições `teste`: ela não escolhe nada, então rodar na validação só
  gastaria tempo;
- roda o modelo produto e o modelo lab quando cada arquivo existir. A flag nova `--sem-lab` pula o
  modelo lab.

- [ ] **Passo 1: escrever os testes que falham**

```python
def test_tipo_por_modelo(tmp_path, monkeypatch, fazer_imagem):
    monkeypatch.setattr(pipeline.leaves, "classify", lambda p, modelo="produto": ("saudavel", 0.9, {}))
    f = fazer_imagem(tmp_path / "f.jpg", 1)
    assert pipeline.process_leaf(f, "x", baseline=False, classificador=True)[0].tipo == "folha_classificador"
    assert pipeline.process_leaf(f, "x", baseline=False, classificador=True, modelo="lab")[0].tipo == "folha_classificador_lab"

def test_itens_folhas_sem_treino(manifestos_falsos):
    import run_batch
    ordem = [(i.conjunto, i.particao) for i in run_batch.itens_folhas()]
    assert ordem == sorted(ordem, key=[("lab", "val"), ("lab", "teste"), ("campo", "val"), ("campo", "teste")].index)
    assert "treino" not in {p for _, p in ordem}
```

- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 8: avaliação por conjunto

**Arquivos:**
- Modificar: `scripts/evaluate.py`: `avalia_baseline` (162), `avalia_classificador` (190),
  `resumo_backend` (260) e `main` (306).
- Teste: `tests/test_evaluate_folhas.py`

**Interfaces:**
- Usa: `ler_nome_folha` (Tarefa 1) e `analise_limiar` (já existe).
- Fornece:
  - `folhas(df, tipo: str) -> pd.DataFrame`: as linhas daquele tipo (para classificador, só
    `campo == "classe"`) com as colunas `conjunto`, `particao` e `real`. Descarta os nomes que
    `ler_nome_folha` não reconhece.
  - `limiar_validacao(f: pd.DataFrame, conjunto: str) -> float | None`: roda `analise_limiar` nas
    linhas de `<conjunto>/val`. Devolve `None` se não houver nenhuma.
    - O produto usa `"campo"`.
    - O modelo lab usa `"lab"`: ele não vê foto de campo nem para escolher o limiar.
  - `avalia_classificador(df, tipo, conjunto, limiar, sufixo="", titulo="", gravar=True) -> dict | None`:
    - usa só a partição `teste` daquele conjunto;
    - os `labels` são as classes presentes em `real` (4 no laboratório, 3 no campo), e prever
      `saudavel` no campo conta como erro;
    - a acurácia passa a ser `certo.mean()`: o `classification_report` não devolve `accuracy`
      quando há previsão fora dos `labels`;
    - a matriz de confusão tem as classes presentes nas linhas e as 4 `CLASSES` nas colunas, para
      as previsões de `saudavel` aparecerem. No JSON ela vira `{"reais", "previstas", "valores"}`;
    - nada é escolhido no teste: a figura do limiar marca o `limiar` recebido;
    - `gravar=False` não grava figura nem tabela, para os testes não escreverem em `report/`;
    - devolve as chaves de hoje, menos `limiar_escolhido`, mais `limiar` e `com_limiar` =
      `{aceitos, precisao_aceitos, erros_barrados, erros_passaram, acertos_barrados}` nesse limiar.
  - `avalia_baseline(df, conjunto, sufixo="", titulo="")`: só a partição `teste`.

**Chaves de `metricas.json`:**
- `classificador`: produto no laboratório, mais `limiar_escolhido`, que é o limiar da validação de
  campo. As telas leem essa chave;
- `classificador_campo`: produto no campo;
- `classificador_lab`: `{"lab": ..., "campo": ...}` para o modelo lab, com o limiar da validação
  de laboratório;
- `baseline` e `baseline_campo`;
- `disputa`: o conteúdo de `config.DISPUTA`, se existir;
- `modelo_avaliado_sha256`: o `sha256` calculado do arquivo `config.LEAF_MODEL`.

**Figuras** (o `sufixo` de cada chamada):
- produto no laboratório: `""`, ou seja, os nomes de hoje (`folhas_matriz_confusao`,
  `folhas_calibracao`, `folhas_limiar`). O relatório e o notebook já usam esses nomes;
- produto no campo: `"_campo"`;
- modelo lab no campo: `"_lab_no_campo"`;
- modelo lab no laboratório: `gravar=False`.

**Tabelas:**
- as de hoje;
- `folhas_por_classe_campo.tex` e `baseline_rotulos_campo.tex`;
- `folhas_lab_vs_campo.tex`: uma linha por modelo × conjunto, com as colunas Acurácia, F1 macro,
  Conf. dos erros, ECE e Erros barrados;
- `disputa_redes.tex`.

**Resumo (`resumo_backend`):** uma seção por chave nova, no formato da seção do classificador. A
disputa vira uma tabela com rede, parâmetros, F1 val. campo, F1 val. lab e tempo.

O `main` mantém as notas e as folhas cujo nome é reconhecido.

- [ ] **Passo 1: escrever os testes que falham.** O auxiliar `linha(conjunto, particao, real,
  previsto, conf, tipo="folha_classificador")` monta uma linha no formato do SQLite.

```python
def test_saudavel_previsto_no_campo_e_erro():
    df = pd.DataFrame([linha("campo", "teste", "ferrugem_comum", "ferrugem_comum", .9),
                       linha("campo", "teste", "cercosporiose", "saudavel", .8),
                       linha("campo", "teste", "helmintosporiose", "helmintosporiose", .7)])
    r = avalia_classificador(df, "folha_classificador", "campo", limiar=0.5, gravar=False)
    assert r["acuracia"] == pytest.approx(2 / 3) and set(r["por_classe"]) == {"cercosporiose", "ferrugem_comum", "helmintosporiose"}
    assert r["matriz_confusao"]["previstas"] == CLASSES and r["matriz_confusao"]["valores"][0][3] == 1

def test_limiar_vem_da_validacao_de_campo():
    val = [linha("campo", "val", "cercosporiose", "ferrugem_comum", c) for c in (.55, .60)] + \
          [linha("campo", "val", "cercosporiose", "cercosporiose", c) for c in (.7, .8, .9)]
    teste = [linha("campo", "teste", "cercosporiose", "helmintosporiose", .9)]
    df = pd.DataFrame(val + teste)
    lim = limiar_validacao(folhas(df, "folha_classificador"), "campo")
    assert lim == pytest.approx(0.65)
    assert avalia_classificador(df, "folha_classificador", "campo", lim, gravar=False)["com_limiar"]["erros_passaram"] == 1

def test_nomes_sem_conjunto_sao_ignorados():
    df = pd.DataFrame([linha("campo", "teste", "cercosporiose", "cercosporiose", .9)])
    df.loc[1] = {**df.loc[0], "arquivo": "demo_folha.jpg"}; df.loc[2] = {**df.loc[0], "arquivo": "cercosporiose/x.jpg"}
    assert list(folhas(df, "folha_classificador").arquivo) == ["campo/teste/cercosporiose/cercosporiose_x.jpg"]
```

  O auxiliar `linha` monta `arquivo = f"{conjunto}/{particao}/{real}/{real}_x.jpg"`,
  `campo = "classe"`, `valor = previsto`, `confidence = conf` e `backend = "local"`. Nomes
  repetidos não importam para essas funções.
- [ ] **Passo 2:** rodar → falha.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar → passa.
- [ ] **Passo 5:** Commit.

### Task 9: dados reais

- [ ] **Passo 1:** `$PY scripts/prepare_leaves.py` → 4 linhas com `treino=450 teste=25`.
- [ ] **Passo 2:** conferir que o teste de laboratório não mudou e que só entraram fotos novas no
  treino:

```bash
git status --porcelain ../data/leaves/test          # vazio
git status --porcelain ../data/leaves/train | grep -v '^??' | wc -l   # 0
```

- [ ] **Passo 3:** `$PY scripts/prepare_campo.py` → o resumo mostra 376 lidas, as repetidas e as
  contagens por partição.
- [ ] **Passo 4:** `du -sh ../data/leaves/campo ../data/leaves/train` → campo com até ~20 MB.
- [ ] **Passo 5:** abrir 10 fotos de campo sorteadas e ver se cada classe é plausível. Anotar
  problemas de rótulo, sem corrigir à mão.
- [ ] **Passo 6:** Commit dos dados e dos manifestos.

### Task 10: disputa e modelos finais

**Arquivos:**
- Criar: `scripts/disputa_redes.py`
- Modificar: `agroflow/leaves/redes.py`. `REDE_PADRAO` passa a ser a vencedora.
- Modificar: `.gitignore` (raiz). Trocar `sojatech_local/models/*.pt` por
  `sojatech_local/models/**/*.pt`. O padrão de hoje não pega `models/disputa/*.pt`, e cada modelo
  tem até 350 MB.

**`disputa_redes.py`:**
- **Opções:** `--redes` (padrão: as 4 da tabela da Tarefa 4, nessa ordem), `--epocas 15` e
  `--rapido`. O `--rapido` chama `treinar(..., epocas=1, max_por_classe=8)` e grava em
  `models/disputa_rapida/`. Não grava `config.DISPUTA` nem copia nada.
- **Para cada rede:** chama `treinar(rede, "lab+campo", config.MODELS / "disputa" / f"{rede}.pt")`
  e junta `{rede, f1_val_campo, acuracia_val_campo, f1_val_lab, n_parametros, tempo_treino_s, lote}`.
- **No fim:**
  - escolhe a vencedora com `escolher_vencedora`;
  - grava `config.DISPUTA` = `{"candidatas": [...], "vencedora": ...}`;
  - copia o `.pt` e o `.json` da vencedora para `config.LEAF_MODEL`;
  - imprime a tabela.

- [ ] **Passo 1:** `$PY scripts/disputa_redes.py --rapido` → 4 linhas, sem falta de memória. Se uma
  rede estourar os 8 GB, reduzir o `lote` dela em `REDES`. O lote efetivo continua 32. Depois,
  apagar `models/disputa_rapida/`.
- [ ] **Passo 2:** `$PY scripts/disputa_redes.py` em segundo plano (~30 a 60 min) →
  `results/disputa_redes.json` com 4 candidatas e a vencedora.
- [ ] **Passo 3:** trocar `REDE_PADRAO` pela vencedora. Rodar
  `$PY scripts/train_leaf_classifier.py --dados lab` → `models/leaf_classifier_lab.pt`.
- [ ] **Passo 4:** `git status --porcelain models` só mostra `.json`. Commit do `.gitignore`, do
  `disputa_redes.json`, do `redes.py` e dos `.json` de `models/`. Os `.pt` ficam fora do Git.

### Task 11: avaliação real e documentação

- [ ] **Passo 1:** `$PY scripts/run_batch.py folhas` → cerca de 560 fotos processadas.
- [ ] **Passo 2:** `$PY scripts/evaluate.py` → o resumo traz laboratório e campo para os dois modelos.
- [ ] **Passo 3:** conferir que as notas não mudaram:
  `git show HEAD:sojatech_local/results/metricas.json` contra o arquivo novo, comparando as chaves
  `notas` e `notas_teste` num `python -c`. Esperado: iguais.
- [ ] **Passo 4:** ler os números.
  - Esperado: o modelo lab cai no campo, e o produto acerta mais no campo que o lab.
  - Se não acontecer, é um achado para o relatório. Não ajustar nada olhando o teste.
- [ ] **Passo 5:** atualizar a documentação:
  - `sojatech_local/README.md`: `prepare_campo`, `disputa_redes`, os argumentos do treino e o
    `pytest`;
  - a célula de treino do notebook do Colab: treinar `--dados lab` e depois o padrão;
  - `docs/STATUS.md`.
- [ ] **Passo 6:** `$PY -c "from agroflow.leaves import modelo_confere; print(modelo_confere())"` →
  `True`.
- [ ] **Passo 7:** `$PY -m pytest tests -q` → tudo passa.
- [ ] **Passo 8:** Commit.
