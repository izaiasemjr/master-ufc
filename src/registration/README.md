# Registro e ablações

O executor suportado lê os YAMLs de `configs/`:

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions
```

`reference_mask` alinha as galerias `N_N_0` pré-processadas à
`bs000_N_N_0` com `pcl_icp`, concatena as nuvens e aplica MLS. No dataset
atual, as opções são `-d 200 -r 50 -i 50` e raio MLS `2.0`.
Essa galeria intermediária constrói a máscara; não é a galeria final de
descritores.

`registration` passa a máscara como `-target_special` ao CP-ICP. Assim, o
registro usa a máscara global, com precedência sobre `target_suffix: N_N_0`.
No experimento base, todas as faces são registradas, com duas partições por
eixo e ICP `0.001,100`. `landmarks` aplica a matriz correspondente às anotações
antes de crop e keypoints.

Os resultados ficam em
`data/results/BOSPHORUS/experiments/<id>/registration/`, incluindo
`reference_mask`, `registrations`, `transforms`, `landmarks_transformed`,
`metrics.csv`, `manifest.csv` e `run.json`.

## Modos

`registration.mode` aceita:

- `all` (padrão): CP-ICP em todas as faces; comportamento original.
- `gallery_only`: CP-ICP somente nas faces que correspondem a
  `dataset.reference.gallery_filename_regex`; as demais seguem sem registro.
- `none`: todas seguem sem registro.

Nos bypasses, a nuvem pré-processada e os landmarks originais são copiados
sem alterar seus bytes. A matriz identidade mantém a interface entre etapas;
nenhum executável de registro/transformação é necessário para essas faces.
O manifest distingue `action=registered`, `bypassed` e `reused`, inclusive
quando uma saída existente é pulada.

Com `gallery_only`, o campo opcional `registration.reuse_gallery_from` aceita
outro ID de experimento do mesmo dataset. Ele preserva as nuvens, matrizes e
landmarks da galeria registrada original. O compilador também direciona o
matching para os descritores originais da galeria, preservando as probes do
novo experimento. Isso controla variações de reexecução, inclusive do ISS.
Artefatos de origem ausentes causam erro, sem reconstrução silenciosa.
Sem esse campo, `gallery_only` registra novamente a galeria e precisa da
máscara global.

As duas ablações preparadas são:

```bash
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_gallery_only_registration
python3 src/pipeline/run.py --experiment bosphorus_neutrals_occlusions_no_registration
```

Elas dispensam `reference_mask`: a primeira reutiliza a galeria original;
a segunda não usa máscara. As demais etapas e parâmetros são preservados.
Consulte [o protocolo e a pesquisa](../../docs/bosphorus_registration_ablation.md)
para os controles e limites da comparação.

## Compilação e validação

```bash
cmake -S src/registration/cp_icp -B src/registration/cp_icp/build
cmake --build src/registration/cp_icp/build --parallel
python3 -m unittest discover -s tests -v
```

O CP-ICP exige PCL. O fluxo original de landmarks exige
`pcl_transform_point_cloud`. Os scripts também aceitam `--config` com o JSON
compilado pelo pipeline, `--project-root`, `--dry-run` e `--overwrite`.
`run_registration.py` aceita ainda `--limit` para testes reduzidos.
`legacy/` preserva scripts históricos com caminhos fixos.
