# Fase 6 — Despliegue (Deployment, formato portfolio)

> CRISP-DM · Fase 6 de 6

En un proyecto de portfolio el "despliegue" es la **comunicación del resultado** a sus distintas
audiencias. Entregables:

| Entregable | Fichero | Audiencia |
|---|---|---|
| **Resumen ejecutivo (1 página)** | `docs/resumen_ejecutivo.md` | Stakeholder no técnico (Product Lead, dirección) |
| **Notebook de presentación** | `notebooks/ab_test_olist.ipynb` (+ fuente `.py` jupytext) | Revisor técnico / reclutador de Data |
| **README del repositorio** | `README.md` | Visitante de GitHub |
| **Borrador de post de LinkedIn** | `docs/linkedin_post.md` | Red profesional |
| **Documentación por fase + auditorías** | `docs/0X_*.md`, `docs/auditoria_*.md` | Traza completa del razonamiento |

## Reproducibilidad

Refactorizada tras la revisión del usuario ("no es reproducible si está todo en un notebook"):

- **Única fuente de verdad de los parámetros:** `params.yaml`, cargado por `src/config.py`. Ningún
  otro módulo define `SEED`, `ALPHA`, la ventana temporal, el modelo de costes, etc. (`tests/
  test_config.py` lo verifica con un análisis del AST).
- **Único entrypoint:** `python run_all.py` corre las 6 fases en orden de dependencia, comprueba que
  cada una genera sus salidas y termina con un **informe de reproducibilidad** (decisión == LANZAR,
  A/A ~5 %, IC del A/B sobre el MDE, sin SRM, guardrails intactos, …). Sale con código ≠ 0 si algo
  no cuadra. ~2 min.
- **Sin rutas de ejecución paralelas:** el notebook `ab_test_olist.ipynb` **solo lee** `outputs/` y
  muestra figuras + narrativa; no recalcula nada. Antes tenía una segunda ruta de cálculo (llamaba a
  `modeling.main()` etc.), que era la crítica válida.
- **`inject_diluted_effect`** vive en `src/effect_model.py` (sin efectos secundarios al importar);
  antes `evaluation.py` lo importaba de `modeling.py`, acoplando las fases.
- **Rutas absolutas** derivadas de la ubicación del repo → funciona desde cualquier CWD.
- **Tests:** `pytest` (rápidos: config, efecto sintético, invariantes de los resultados) y
  `pytest -m slow` (re-ejecuta `modeling.main()` dos veces y comprueba que el JSON es idéntico).
- Los CSV crudos de Olist **no se versionan** (licencia CC BY-NC-SA 4.0).
- `notebooks/ab_test_olist.py` (jupytext *percent*) es la fuente versionable del notebook.

## Recomendación de comunicación (LinkedIn)

El ángulo elegido no es "hice un A/B test" (genérico) sino el **hallazgo metodológico**: corregir
por comparaciones múltiples no protege frente al p-hacking si el *estimando* está mal planteado
(medir el efecto en valor absoluto en vez de en porcentaje, sobre cortes correlacionados con el
tamaño de cesta, fabrica "segmentos ganadores" que sobreviven incluso a Bonferroni). Es un punto
concreto, contraintuitivo y demostrado con código.

## Qué NO se entrega (y por qué)

- **No hay recomendación de despliegue técnico real** (feature flags, rollout progresivo,
  monitorización en producción): el efecto es simulado y no hay sistema que desplegar. El resumen
  ejecutivo sí incluye la lista de métricas a vigilar *si el experimento fuera real*.
- **No hay modelo predictivo**: es un proyecto de inferencia causal / experimentación, no de ML.
