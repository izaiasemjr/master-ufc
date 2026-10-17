# Estado atual do projeto

## 2026-10-16 — foco em Bosphorus neutros + oclusões

- Única configuração de experimento: `configs/experiments/bosphorus_neutrals_occlusions.yaml`.
- Configuração da base: `configs/datasets/bosphorus.yaml`.
- Galeria: `N_N_0`; probes: demais neutras e oclusões EYE, GLASSES, MOUTH e HAIR.
- Parâmetros do experimento preservados; execução sequencial com um worker.
- Removidos os outros YAMLs, o template, as auditorias, a extensão de reutilização de máscara/galeria e as alterações de paralelismo associadas.
- Removidos os resultados anteriores para permitir uma execução do zero.
- Base original, landmarks, código das etapas e executáveis compilados preservados.
- Resultados novos: `data/results/BOSPHORUS/experiments/bosphorus-neutrals-occlusions/`.
- Consulte o README para validar, executar e localizar as tabelas de avaliação.
- Mais amostras e novos experimentos serão tratados posteriormente.
