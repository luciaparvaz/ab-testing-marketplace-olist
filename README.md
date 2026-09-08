# A/B Testing en un marketplace — ¿un rediseño de la ficha de producto aumenta el AOV?

> Proyecto de portfolio · metodología **CRISP-DM** · dataset **Brazilian E-Commerce by Olist**
> Estado: **en construcción** — Fase 1 (Business Understanding) cerrada.

Análisis de experimentación de producto sobre un marketplace real: se evalúa si un rediseño de la
ficha de producto (recomendaciones de cross-sell + barra de progreso hacia envío gratis) incrementa
el **valor medio del pedido (AOV)** sin dañar la satisfacción ni las cancelaciones.

Como el dataset no trae grupos control/tratamiento, la asignación se **simula de forma declarada** y
se ejecutan dos experimentos: un **test A/A** (validación del control de falsos positivos) y un
**test A/B con efecto sintético conocido** (δ = 5 %), cuyo objetivo es demostrar que el diseño y el
análisis recuperan sin sesgo un efecto de tamaño conocido.

## Estructura

| Ruta | Contenido |
|---|---|
| `docs/01_business_understanding.md` | **Fase 1** — problema, H0/H1, métrica primaria, guardrails, MDE, diseño de la simulación |
| `data/raw/` | CSVs de Olist (no versionados — ver más abajo) |
| `src/` | Módulos de preparación, simulación de asignación, potencia y análisis |
| `notebooks/` | Notebook final reproducible con narrativa CRISP-DM |
| `outputs/` | Figuras y tablas generadas |

## Datos

Dataset: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
· Licencia **CC BY-NC-SA 4.0** (uso no comercial) · ~45 MB · 9 CSVs relacionales.

No se versionan los datos crudos por la licencia. Para reproducir, coloca los 9 CSVs en `data/raw/`:

```bash
# opción con kaggle CLI (requiere ~/.kaggle/kaggle.json)
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
```

## Reproducir

```bash
pip install -r requirements.txt
jupyter notebook notebooks/
```
