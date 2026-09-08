# Fase 5 — Evaluación (Evaluation)

> CRISP-DM · Fase 5 de 6
> Script reproducible: `src/evaluation.py` → `outputs/tables/fase5_resumen.json`,
> `outputs/tables/fase5_segmentos.csv` · Figura: `outputs/figures/f5_01_forest_segmentos.png`

Traduce el resultado estadístico de la Fase 4 a una **decisión de producto**, separando
significancia de relevancia y controlando el p-hacking en el análisis por segmentos.

---

## 5.1 Resultado con reporte completo (no solo p-valor)

| Métrica primaria — AOV (efecto diluido inyectado) | Welch **winsor p99,5** | Welch **crudo** |
|---|---|---|
| Lift relativo | **+5,67 %** | **+6,11 %** |
| IC 95 % | [+3,99 % ; +7,34 %] | [+4,09 % ; +8,13 %] |
| p-valor | 3,1·10⁻¹¹ | 3,1·10⁻⁹ |
| Efecto verdadero inyectado (+5,0 %) | **dentro del IC** | **dentro del IC** |

n = control 47.280 · treatment 47.423.

**Lectura del estimador puntual:** ambas versiones quedan por encima del +5 % inyectado por el
**desbalance basal del split** `SEED=42` (+1,2 %, no significativo, p = 0,235; Fase 3). El A/B
multi-semilla (Fase 4 §4.6) confirma que **en crudo el estimador es insesgado** (−0,03 pp sobre 500
réplicas, cobertura del IC 0,94) y que la **winsorización lo atenúa −0,36 pp** (a cambio de menor
varianza). Rango honesto del tamaño del efecto: **+5,7 % a +6,1 %**. La decisión se ancla en el
**IC**, no en el punto — y ambos IC superan el MDE.

---

## 5.2 Significancia estadística ≠ relevancia de negocio

| Pregunta | Criterio | Resultado |
|---|---|---|
| ¿Es **estadísticamente** significativo? | p < 0,05 | **Sí** (p ≈ 3·10⁻¹¹) |
| ¿Es **relevante para el negocio**? | IC 95 % del lift **enteramente por encima** del MDE de relevancia (+3 %) | **Sí** — IC [+3,99 % ; +7,34 %] (winsor) e [+4,09 % ; +8,13 %] (crudo) |

Con n ≈ 47 k/grupo, un efecto trivial también saldría "significativo". Lo que hace **accionable**
este resultado es que **todo el intervalo de confianza está por encima del umbral de relevancia de
negocio**, no solo el estimador puntual.

> El MDE de relevancia (+3 %) está **derivado de un modelo de break-even** (`src/mde_cost_model.py`,
> `f_mde_breakeven.png`): es el lift por debajo del cual el margen incremental no cubre el coste de
> propiedad del rediseño. Válido para un marketplace con ≥ ~415 k pedidos/año (payback 2 años).

### Impacto económico estimado

| | Valor |
|---|---|
| Pedidos válidos/año (extrapolación del histórico) | ≈ 58.700 |
| GMV de mercancía anual (base) | ≈ R$ 8,05 M |
| **Uplift de GMV anual** | **+R$ 456.000** · IC 95 % [+R$ 322 k ; +R$ 591 k] |
| Uplift de ingreso del marketplace (comisión asumida 15 %) | ≈ +R$ 68.000/año |

*Extrapolación lineal del lift por pedido al volumen anual; el ingreso real depende del take rate.*

---

## 5.3 Estimación ajustada por covariables (ANCOVA) — reducción de varianza

OLS `AOV_w ~ treatment + n_items + freight + categoría + macro-región + trimestre` (errores HC3):

| | Lift | IC 95 % | SE (R$) |
|---|---:|---:|---:|
| Sin ajuste | +5,67 % | [+3,99 % ; +7,34 %] | 1,141 |
| **Con ajuste** | **+5,19 %** | **[+3,71 % ; +6,68 %]** | **1,013** |

El ajuste por covariables **reduce el error estándar un 11,2 %** (IC más estrecho) y **acerca el
estimador al +5 % verdadero** — las covariables (sobre todo nº de ítems y categoría) explican parte
del ruido residual. Es la técnica estándar (CUPED / regresión) para ganar precisión sin sesgo.

---

## 5.4 Análisis por segmentos — pre-especificado y con corrección

**Segmentos declarados ANTES de mirar resultados:** `cesta` (1 vs 2+ ítems), `payment_type`,
`macro_region` (5 macrorregiones de Brasil), `trimestre`, `cat_grupo` (6 categorías top + resto).

> **"Nuevos vs. recurrentes" queda fuera de alcance**, declarado: la dedup a 1 pedido/cliente lo
> deja degenerado (n_recurrente ≈ 40) y la recompra en Olist es ~3 % (Fase 2 §2.7). Se analizaría
> sobre la tabla de robustez con todos los pedidos.

### Test de interacción `treatment × segmento` sobre **log(AOV)**, Wald **HC3** (efecto relativo)

> HC3 (SE robustas a heterocedasticidad): necesario porque bajo H1 las varianzas de grupo difieren
> (Fase 4; auditoría Fase 5 §A2). El F-test homocedástico daría p ligeramente distintos sin cambiar
> la conclusión.

| Segmento | p bruto | p ajustado (BH) | ¿Heterogéneo? |
|---|---:|---:|:--:|
| cesta | 0,92 | 0,92 | ❌ |
| payment_type | 0,38 | 0,92 | ❌ |
| macro_region | 0,68 | 0,92 | ❌ |
| trimestre | 0,79 | 0,92 | ❌ |
| cat_grupo | 0,14 | 0,68 | ❌ |

**Ninguna interacción significativa.** El efecto **relativo** es homogéneo entre segmentos, coherente
con el diseño (los respondedores se sortean al azar). En el *forest plot* (`f5_01`) un par de
segmentos pequeños y ruidosos (p. ej. `bed_bath_table`, `health_beauty`) se alejan visualmente del
+5,7 % global, pero son los **outliers esperados al mirar 25 niveles a la vez** con IC marginales
(no simultáneos): el test de interacción conjunto —que es el contraste correcto— no detecta
heterogeneidad, y `health_beauty` es precisamente el único hallazgo nominal que **no sobrevive a la
corrección** (§5.5).

> **Por qué el test se hace en `log` y no en nivel:** el efecto es multiplicativo, así que el lift
> **absoluto** en R$ es mecánicamente mayor en cestas grandes. Un test en nivel detectaría esa
> "heterogeneidad" que no es real — la pregunta de negocio es si el **%** cambia, y eso se contrasta
> en escala logarítmica.

---

## 5.5 El riesgo de p-hacking — demostrado

Se prueban **38 cortes exploratorios arbitrarios** (estados sueltos, categorías sueltas, cuartiles
de flete, trimestres). Test: interacción `treat × corte`, Wald **HC3**. Esperados por puro azar a
α = 0,05: **≈ 1,9**.

| Escala del test | Nominales p < 0,05 | Tras BH (FDR) | Tras Bonferroni |
|---|---:|---:|---:|
| **Nivel (R$)** | **5** (3 en cuartiles de flete) | **3** (`flete_q1`, `flete_q4`, `bed_bath_table`) | **2** |
| **Log (efecto relativo, %)** | 2 | **0** | **0** |

**Lecciones:**
1. En **nivel**, varios "segmentos donde el efecto es distinto" **sobreviven incluso a Bonferroni**.
   No son casualidad: son un **artefacto mecánico** del efecto multiplicativo (el lift en R$ es mayor
   en cestas grandes), concentrado en los cortes correlacionados con el tamaño (cuartiles de flete).
2. En **log** (la magnitud correcta: el %), solo quedan hallazgos nominales de nivel-azar y
   **ninguno sobrevive** a BH ni a Bonferroni.
3. → **(a)** testar la magnitud correcta (%, no R$ absolutos); **(b)** pre-especificar los segmentos;
   **(c)** corregir por multiplicidad. **Corregir no basta si el estimando está mal planteado.**

---

## 5.6 Decisión de producto

# 🟢 LANZAR

| Criterio | ✔ |
|---|---|
| Efecto primario significativo (p ≈ 3·10⁻¹¹) | ✅ |
| IC 95 % del lift enteramente por encima del MDE de relevancia (+3 %) | ✅ [+3,99 % ; +7,34 %] |
| Estimación robusta (winsor, log, bootstrap, ANCOVA todas concordantes) | ✅ |
| Ningún guardrail degradado (G1–G4, Benjamini-Hochberg) | ✅ |
| Efecto relativo homogéneo entre segmentos pre-especificados | ✅ |
| Impacto económico material (+R$ 456 k/año GMV) | ✅ |

**Caveats declarados:**
- El efecto es **sintético y conocido**: esta decisión **valida el proceso de decisión**, no
  constituye un hallazgo real sobre Olist.
- Con un ATE inyectado de +2 % o +3 %, la misma regla habría devuelto **ITERAR** (efecto real pero
  IC tocando el MDE); con +0 %, **NO LANZAR** (Fase 4 §4.5). Las tres ramas funcionan.

---

## 5.7 Limitaciones de la evaluación

1. **Efecto simulado** (ya tratado): sin validez externa; el objetivo es demostrar el método.
2. **Extrapolación económica lineal**: el uplift de GMV asume que el lift por pedido se mantiene al
   escalar a todo el volumen y en el tiempo; ignora novedad, saturación y estacionalidad.
3. **Sin métrica de retención / LTV**: la ventana y la recompra baja de Olist lo impiden. Un
   guardrail de recompra a 90 días sería deseable en un experimento real.
4. **Guardrails sin efecto inyectado**: por diseño salen planos. Un experimento real vigilaría
   además devoluciones y reclamaciones (no disponibles en Olist).
5. **Un solo split de análisis** (SEED = 42): el estimador puntual carga el desbalance basal de esa
   asignación; mitigado con el IC, la ANCOVA y la evidencia de insesgadez sobre 1.000 réplicas.

---

## 5.8 Cierre de la Fase 5 y traspaso a la Fase 6

- [x] Reporte completo: efecto, IC, p, tamaño, n — no solo significancia.
- [x] Significancia (p ≈ 3·10⁻¹¹) **vs** relevancia (IC entero sobre el MDE +3 %) — ambas ✅.
- [x] Impacto económico: +R$ 456 k/año de GMV [IC +R$ 322 k ; +R$ 591 k].
- [x] ANCOVA: −11,2 % de SE, estimador más cerca del valor real.
- [x] Segmentos pre-especificados + BH: **sin heterogeneidad**.
- [x] p-hacking demostrado (nivel vs log; BH vs Bonferroni).
- [x] **Decisión: LANZAR**, con las tres ramas de la regla verificadas.
- **Siguiente (Fase 6 — Deployment):** resumen ejecutivo de 1 página, notebook reproducible con
  narrativa, README de GitHub, borrador de post de LinkedIn.
