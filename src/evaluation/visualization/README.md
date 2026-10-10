# Visualização da avaliação

Esta etapa transforma os CSVs de `evaluation/` em figuras que ficam no próprio
resultado do experimento:

```text
evaluation/
  <variante>/accuracy_by_k.csv
  <variante>/cmc.csv
  visualization/
    <variante>/rr_by_k.png
    <variante>/cmc_k_<k>.png
```

`rr_by_k` corresponde à análise de variação de `k` do script R histórico.
`cmc_k_<k>` corresponde à variação de rank com `k` fixo. O valor de `k` por
variante vem de `visualization.cmc_k` no YAML. PNG é o padrão; `formats` também
aceita `pdf` e `svg`.

O runner usa Matplotlib com backend sem interface gráfica, portanto funciona em
WSL/servidor e salva arquivos de 300 DPI por padrão.
