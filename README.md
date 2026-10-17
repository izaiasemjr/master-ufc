# master-results-UFC

Pipeline configurável de reconhecimento facial 3D. Ela pré-processa nuvens de
pontos, constrói a máscara de referência, registra e recorta as faces, extrai
keypoints e descritores FPFH, executa matching, classificação e avaliação.

O repositório contém **código, configurações e documentação**. Bases biométricas,
nuvens `.pcd` e resultados nunca são publicados nele.

## Requisitos e instalação

O ambiente suportado para executar toda a pipeline é **Ubuntu/Debian ou WSL**,
pois as etapas nativas usam PCL. No WSL, abra a distribuição Linux e execute:

```bash
git clone <URL-DO-REPOSITORIO> master-researches
cd master-researches
bash scripts/install_dependencies.sh
```

O instalador usa `apt` para instalar Python 3, Matplotlib, CMake, compilador
C++ e PCL (incluindo os utilitários de linha de comando), e então compila os
seis executáveis nativos do projeto. Ele pede `sudo` somente para os pacotes do
sistema. Para ambientes já preparados, há duas opções:

```bash
# Apenas conferir as ferramentas existentes e compilar.
bash scripts/install_dependencies.sh --skip-system-packages

# Instalar/verificar pacotes sem recompilar.
bash scripts/install_dependencies.sh --skip-build
```

Não é necessário instalar uma biblioteca Python adicional para o executor: o
leitor YAML usado pela pipeline faz parte do próprio projeto. Em uma instalação
manual, são necessários: Python 3, `python3-matplotlib`, CMake, um compilador
C++ compatível e PCL com os programas `pcl_icp`, `pcl_voxel_grid`,
`pcl_outlier_removal`, `pcl_transform_point_cloud`,
`pcl_concatenate_points_pcd` e `pcl_mls_smoothing`.

## Dados locais e privacidade

Baixe o Bosphorus somente a partir da fonte autorizada e conforme os seus
termos de uso. Não copie o conteúdo da base para este repositório nem para um
fork público. O `.gitignore` protege integralmente `data/bases/` e
`data/results/`, preservando apenas seus `.gitkeep` vazios; além disso, ele
ignora qualquer arquivo `*.pcd` em todo o projeto.

Após descompactar a base localmente, organize-a assim (os nomes de exemplo são
apenas estruturais; não são dados incluídos no repositório):

```text
data/
  bases/
    BOSPHORUS_PCD/
      bs000/
        <nuvem>.pcd
      ...
    LANDMARKS_PCD/
      bs000/
        <landmarks>.pcd
      ...
  results/                         # criado/preenchido pela pipeline; não versionado
```

Esses caminhos correspondem a `configs/datasets/bosphorus.yaml`. Caso a cópia
local da base tenha outro nome ou organização, altere somente os campos
`paths.raw_clouds` e `paths.landmarks` desse arquivo de configuração. Não
guarde essa alteração em `data/`.

O experimento ativo seleciona apenas dois grupos:

- `neutral`: `bs<subject>_N_N_<sample>.pcd`;
- `occlusion`: `bs<subject>_O_<EYE|GLASSES|MOUTH|HAIR>_<sample>.pcd`.

A galeria usa `N_N_0` de cada sujeito; as demais neutras (`N_N_1`,
`N_N_2`, etc.) e as oclusões são probes. As contagens são inferidas dos
arquivos disponíveis. Expressões e outras poses da base não entram neste
experimento. Os arquivos originais da base e os landmarks são preservados.

Para a descrição acadêmica da base e de suas convenções, consulte Savran et
al., *Bosphorus Database for 3D Face Analysis* (2008),
[DOI: 10.1007/978-3-540-89991-4_6](https://doi.org/10.1007/978-3-540-89991-4_6).

## Executar a pipeline

O único experimento configurado é
[`bosphorus_neutrals_occlusions.yaml`](configs/experiments/bosphorus_neutrals_occlusions.yaml).
Ele executa toda a cadeia para neutros + oclusões, com as variantes Radial
Grid (`sparse_15`), SIFT e ISS.

Primeiro valide a configuração e os caminhos, sem criar arquivos:

```bash
python3 src/pipeline/run.py \
  --experiment bosphorus_neutrals_occlusions \
  --dry-run
```

Quando o resultado do teste estiver correto, execute a cadeia completa:

```bash
python3 src/pipeline/run.py \
  --experiment bosphorus_neutrals_occlusions
```

Os resultados desse exemplo são criados exclusivamente em:

```text
data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/
```

Também é possível executar uma etapa, desde que as etapas das quais ela depende
já tenham sido concluídas:

```bash
python3 src/pipeline/run.py \
  --experiment bosphorus_neutrals_occlusions \
  --stage preprocessing
```

As etapas disponíveis são `preprocessing`, `reference_mask`, `registration`,
`landmarks`, `crop`, `keypoints`, `feature_extraction`, `matching`,
`classification`, `evaluation` e `visualization`. Use `--overwrite` somente
para regenerar saídas existentes e `--print-config` para inspecionar o contexto
YAML resolvido.

## Resultados e reprodutibilidade

Cada execução registra o contexto expandido em `pipeline/resolved-context.json`
e o resultado das etapas em `pipeline/pipeline-run.json`, dentro do diretório
do experimento. As saídas incluem manifests por etapa, descritores, scores,
predições, tabelas CSV de taxa de reconhecimento/CMC e figuras de avaliação.
Nada sob `data/results/` é adicionado ao Git.

## Avaliar este experimento

Após a execução completa, consulte dentro do diretório do experimento:

- `pipeline/pipeline-run.json`: etapas executadas e falhas;
- `evaluation/<variante>/accuracy_by_k.csv`: acurácia por k e categoria;
- `evaluation/<variante>/cmc.csv`: curvas CMC em formato tabular;
- `evaluation/visualization/`: gráficos gerados.

As categorias separam neutras, olho, óculos, boca e cabelo, além dos
agrupamentos de oclusões e de todas as probes. Os valores de k e os seletores
estão no YAML do experimento.

A limpeza removeu os resultados anteriores. A próxima execução completa
recriará a máscara de referência e todas as saídas a partir da base local.
Evite `--limit` na execução usada para avaliação: ele reduz a população
processada nas etapas iniciais.

A ampliação da população e a criação de novos experimentos ficam para uma
próxima etapa, depois da avaliação deste protocolo.
