# Feature extraction (FPFH)

Esta etapa gera um descritor FPFH para cada keypoint de uma face já recortada.
Ela preserva a metodologia do código de dissertação: normais são estimadas na
nuvem facial completa; FPFH é calculado nos keypoints usando essa nuvem como
superfície de busca.

## Compilação

No Linux/WSL, com PCL instalado:

```bash
cmake -S src/feature_extraction -B src/feature_extraction/build
cmake --build src/feature_extraction/build --parallel
```

O binário resultante é `src/feature_extraction/build/feature_extraction`.

## Execução por experimento

O comando recomendado usa o contexto YAML global:

```bash
python3 src/pipeline/run.py \
  --experiment bosphorus_neutrals_occlusions \
  --stage feature_extraction
```

Valide as entradas sem escrever resultados:

```bash
python3 src/pipeline/run.py \
  --experiment bosphorus_neutrals_occlusions \
  --stage feature_extraction --dry-run
```

Cada variante em `feature_extraction.variants` do experimento declara:

- `keypoint_family`: `grids` ou `detectors`;
- `keypoint_method`: nome da pasta produzida pela etapa de keypoints;
- `normal_radius`: raio para estimação das normais;
- `feature_radius`: raio do descritor FPFH.

Os descritores são escritos em:

```text
data/results/<BASE>/experiments/<TESTE>/feature_extraction/
  <VARIANTE>/descriptors/<sujeito>/<amostra>-desc.pcd
```

O runner mantém a relação um-para-um entre keypoints e descritores, valida o
número de pontos de cada PCD e grava `manifest.csv` e `run.json`. Cada saída é
publicada atomicamente; uma extração interrompida não é tratada como resultado
válido. Falhas individuais mantêm diagnóstico completo em
`errors/<VARIANTE>/<sujeito>/<amostra>.log` e serão incluídas no resumo da
pipeline.
