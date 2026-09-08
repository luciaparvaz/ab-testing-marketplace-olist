# Fase 6 — Despliegue (Deployment, formato portfolio)

> CRISP-DM · Fase 6 de 6

En un proyecto de portfolio el "despliegue" es la **comunicación del resultado** a sus distintas
audiencias. Entregables:

| Entregable | Fichero | Audiencia |
|---|---|---|
| **Resumen ejecutivo (1 página)** | `docs/resumen_ejecutivo.md` | Stakeholder no técnico (Product Lead, dirección) |
| **Notebook reproducible con narrativa** | `notebooks/ab_test_olist.ipynb` (+ fuente `.py` jupytext) | Revisor técnico / reclutador de Data |
| **README del repositorio** | `README.md` | Visitante de GitHub |
| **Borrador de post de LinkedIn** | `docs/linkedin_post.md` | Red profesional |
| **Documentación por fase + auditorías** | `docs/0X_*.md`, `docs/auditoria_*.md` | Traza completa del razonamiento |

## Reproducibilidad

- Todas las semillas fijadas (`SEED = 42`); resultados deterministas.
- El notebook se ejecuta de punta a punta con
  `jupyter nbconvert --to notebook --execute --inplace notebooks/ab_test_olist.ipynb`
  (~1 min) y regenera todas las figuras y tablas.
- Los CSV crudos de Olist **no se versionan** (licencia CC BY-NC-SA 4.0); el README explica cómo
  obtenerlos.
- `notebooks/ab_test_olist.py` (formato jupytext *percent*) es la fuente versionable del notebook,
  apta para *diff* y *code review*.

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
