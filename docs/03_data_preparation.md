# Fase 3 — Preparación de los datos (Data Preparation)

> CRISP-DM · Fase 3 de 6
> Scripts reproducibles: `src/prepare_data.py` (tabla analítica + asignación) · `src/balance_check.py`
> Salida: `data/processed/analytical_table.parquet` · `outputs/tables/fase3_transformaciones.csv`
> · `outputs/tables/fase3_balance.csv` · `outputs/figures/f3_01_balance.png`

Limpieza **dirigida a la pregunta experimental** (efecto del rediseño sobre el AOV), no EDA
genérica. Cada transformación queda registrada con su recuento y su justificación.

---

## 3.1 Cadena de transformaciones (traza completa)

| Paso | n antes | n después | Δ | Justificación |
|---|---:|---:|---:|---|
| Crudo (`olist_orders`) | 99.441 | 99.441 | — | — |
| **Ventana temporal** `[2017-01-01, 2018-09-01)` | 99.441 | 99.092 | −349 | Elimina el arranque residual de 2016 y la cola incompleta de sep-oct 2018. Ajuste **por realismo**, no correctivo: el AOV medio no se mueve (auditoría §B6). |
| **Estados válidos** {delivered, shipped, invoiced, approved, processing} | 99.092 | 97.905 | −1.187 | Un pedido pagado es "compra realizada". Se excluyen `canceled` / `unavailable` / `created` (no representan una compra efectiva). Se conserva `is_delivered` para el análisis de sensibilidad. |
| **Pedidos con ítems** | 97.905 | 97.905 | 0 | Los 775 pedidos sin líneas en `order_items` ya cayeron con los estados no válidos. |
| **Dedup a 1 pedido / cliente** (el primero) | 97.905 | 94.703 | −3.202 | Unidad de aleatorización = unidad de análisis (auditoría §B3). Desplaza el AOV medio −0,35 %; elimina la necesidad de errores estándar por clúster. |

**Tabla analítica final: 94.703 filas × 15 columnas · grano = 1 pedido-cliente.**

---

## 3.2 Enriquecimiento (variables construidas)

| Columna | Construcción | Uso |
|---|---|---|
| `merch_value` | Σ `order_items.price` por `order_id` | **métrica primaria (AOV)** — sin winsorizar, para descriptivos |
| `merch_value_w` | `merch_value` recortado en **p99,5 = R$ 1.360** (473 pedidos, 0,50 %) | **métrica primaria para el contraste** (auditoría §B4); se reporta el test con y sin |
| `freight_value` | Σ `order_items.freight_value` por `order_id` | guardrail G3 + covariable de balance |
| `n_items` | recuento de líneas por `order_id` | covariable de balance / diagnóstico |
| `review_score` | reseña de `review_answer_timestamp` **más reciente** por pedido | guardrail G1 |
| `cat_dominante` | categoría (EN) del ítem **más caro** del pedido | covariable de balance / segmentación exploratoria |
| `payment_type` | tipo de la fila de mayor `payment_value`; `not_defined` → `desconocido` | covariable de balance / segmentación |
| `customer_state` | de `olist_customers` vía `customer_id` | covariable de balance / segmentación |
| `mes_compra` | `order_purchase_timestamp` truncado a mes | covariable de balance (estacionalidad) |
| `is_delivered` | `order_status == 'delivered'` | análisis de sensibilidad |
| `group` | ver §3.4 | brazo del experimento |

### Nulos en la tabla final

| Columna | Nulos | Tratamiento |
|---|---:|---|
| `review_score` | 696 (0,73 %) | Se excluyen del test de G1 (análisis de casos completos); dado el 0,7 %, el sesgo potencial es despreciable. Sensibilidad: imputación por la mediana. |
| resto de columnas | 0 | — |

---

## 3.3 *El gotcha* de Olist — resuelto explícitamente

`orders.customer_id` es **único por pedido** (una fila por pedido); la persona real es
`customers.customer_unique_id`. Todo el pipeline (dedup, asignación, conteo de clientes) usa
`customer_unique_id`. Verificado en la auditoría (§A).

---

## 3.4 Asignación aleatoria simulada

- **Unidad:** `customer_unique_id` (equivalente a pedido tras la dedup).
- **Mecanismo:** `numpy.random.default_rng(SEED=42).choice(["control", "treatment"])` por fila.
- **Semilla declarada:** `SEED = 42` (fijada en `src/prepare_data.py`).
- **Resultado:** control = **47.280** · treatment = **47.423** (50,08 % treatment — desviación
  esperada del 50 % por azar en n ≈ 95 k).
- **El efecto de tratamiento NO se inyecta en esta fase.** La tabla sale con la métrica primaria
  intacta; la perturbación (modelo diluido, §1.7b) se aplica en la Fase 4.

---

## 3.5 Covariate balance check (`src/balance_check.py`)

Criterios: **|SMD| < 0,10** por covariable y **test ómnibus no significativo** a α = 0,05.

| Covariable | Tipo | SMD | Test | p-valor | ¿Balanceada? |
|---|---|---:|---|---:|:--:|
| `n_items` | continua | −0,0036 | Welch-t | 0,579 | ✅ |
| `freight_value` | continua | 0,0067 | Welch-t | 0,305 | ✅ |
| `customer_state` | categórica (27) | 0,0127 | χ² (dof 26) | 0,919 | ✅ |
| `cat_dominante` | categórica (72) | 0,0200 | χ² (dof 71) | 0,320 | ✅ |
| `payment_type` | categórica (4) | 0,0085 | χ² (dof 3) | 0,623 | ✅ |
| `mes_compra` | categórica (20) | 0,0153 | χ² (dof 19) | 0,693 | ✅ |

**Todas las |SMD| ≤ 0,02** (muy por debajo de 0,10) y **ningún test ómnibus es significativo**
(p mínimo 0,32). Ver `f3_01_balance.png`. → **Los grupos son intercambiables.**

### Chequeo A/A puntual sobre la métrica primaria (SEED = 42)

| | control | treatment | diferencia | Welch-t |
|---|---:|---:|---:|---:|
| `merch_value` | R$ 137,04 | R$ 138,67 | **+1,63 R$ (+1,19 %)** | **p = 0,235** |

Con la semilla declarada, la diferencia observada en el AOV es **ruido de muestreo** (no
significativa). Es un buen recordatorio de que **una diferencia bruta del ~1 % entre dos grupos
aleatorios es normal** — de ahí la necesidad del test formal y no del ojo. La **calibración global**
(¿la tasa de falsos positivos es realmente ~5 %? ¿los p-valores son uniformes?) se valida con
**1.000 semillas en la Fase 4**.

---

## 3.6 Cierre de la Fase 3 y traspaso a la Fase 4

- [x] Ventana temporal aplicada (2017-01 → 2018-08).
- [x] Estados válidos filtrados; `is_delivered` conservado para sensibilidad.
- [x] Reseñas deduplicadas por `review_answer_timestamp`.
- [x] Dedup a 1 pedido/cliente (94.703 filas).
- [x] Winsorización p99,5 en columna separada `merch_value_w` (solo para el contraste).
- [x] Asignación simulada 50/50 por cliente, `SEED = 42`.
- [x] Covariate balance check **superado** (|SMD| ≤ 0,02; todos los ómnibus no significativos).
- [x] Tabla analítica persistida en `data/processed/analytical_table.parquet`.
- **Siguiente (Fase 4 — Modeling):** power analysis (a priori, con el efecto diluido), verificación
  de supuestos del test, A/A sobre 1.000 semillas (error tipo I + uniformidad de p-valores),
  inyección del efecto diluido y ejecución del test primario + guardrails con corrección BH.
