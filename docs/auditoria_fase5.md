# Auditoría — Fase 5 (Evaluation)

> Revisión crítica previa al cierre de la fase y a la Fase 6.
> Método: re-derivación independiente (`/tmp/audit_f5.py`), revisión de supuestos de cada test.
> Veredicto: **1 corrección aplicada** (SE robustas en los tests de interacción). El resto de
> números y la decisión (**LANZAR**) se confirman sin cambios.

---

## A. Corrección aplicada — SE robustas (HC3) en los tests de interacción

### A1. El problema

Los tests de interacción `treatment × segmento` (§5.4) y el barrido de p-hacking (§5.5) usaban el
**F-test homocedástico** de OLS. Pero la Fase 4 (§4.2) ya demostró que **bajo H1 las varianzas de
grupo NO son iguales** (el efecto diluido infla la varianza del *treatment*).

### A2. Verificación

| Escala | Levene (igualdad de varianzas entre grupos) |
|---|---|
| Nivel (`merch_value_w`) | p = 8·10⁻⁸ → **heterocedasticidad fuerte** |
| Log(`merch_value`) | p = 0,019 → heterocedasticidad **leve** (var 0,862 vs 0,886) |

### A3. Corrección

Se sustituye el F-test homocedástico por un **Wald test con errores HC3** en:
- `src/evaluation.py :: interaction_wald_hc3()` (§5.4)
- el barrido de p-hacking (§5.5), `OLS(...).fit(cov_type="HC3")`

### A4. Impacto en los resultados

**§5.4 — segmentos pre-especificados:** la conclusión **no cambia** (ninguna interacción
significativa). Solo se mueven los p-valores:

| Segmento | p (F-homoc, antes) | p (Wald HC3, ahora) |
|---|---:|---:|
| cesta | 0,93 | 0,92 |
| payment_type | 0,41 | 0,38 |
| macro_region | 0,62 | 0,68 |
| trimestre | 0,80 | 0,79 |
| cat_grupo | 0,26 | 0,14 |

**§5.5 — p-hacking:** el resultado **se refuerza**. Con SE correctas, el problema del test en NIVEL
es **mayor** de lo que se había reportado:

| Escala | Nominales | Tras BH | Tras Bonferroni |
|---|---:|---:|---:|
| Nivel — **F-homoc (reporte anterior)** | 4 | 1 | 1 |
| Nivel — **Wald HC3 (corregido)** | **5** | **3** | **2** |
| Log — Wald HC3 | 2 | 0 | 0 |

La lección es ahora más nítida: en la escala equivocada, los artefactos mecánicos del efecto
multiplicativo **sobreviven incluso a Bonferroni**; en la escala correcta (log), nada sobrevive.
**Corregir por multiplicidad no salva un estimando mal planteado.**

---

## B. Verificaciones que pasan sin cambios

### B1. Resultado primario (§5.1)

Re-derivado de forma independiente (inyección del efecto con `SEED=42`, Welch a mano):

| | Reportado | Re-derivado |
|---|---|---|
| Lift AOV (winsor) | +5,666 % | +5,666 % |
| IC 95 % | [+3,994 % ; +7,337 %] | [+3,994 % ; +7,337 %] |
| Respondedores reales | — | 19,96 % (declarado 20 %) |
| Factor medio treatment | — | 1,0496 (declarado 1,05) |

### B2. ANCOVA (§5.3)

| | Valor | Comprobación |
|---|---|---|
| R² del modelo con covariables | **0,204** | explica el 20 % de la varianza del AOV |
| Reducción de SE | 1,141 → 1,013 = **−11,2 %** | coherente: 1−√(1−0,204) ≈ 11 % |
| Estimador | +5,67 % → **+5,19 %** | confirmado con un modelo alternativo de 2 covariables: +5,25 % |

La **reducción de SE es el beneficio robusto y generalizable**. El desplazamiento del punto
(+5,67 → +5,19) es consistente pero en parte específico de esta muestra; no se vende como propiedad
general.

### B3. Impacto económico (§5.2)

| | Reportado | Re-derivado |
|---|---|---|
| Pedidos válidos/año | ≈ 58.700 | 58.743 (97.905 / 20 × 12) |
| GMV mercancía anual | R$ 8,05 M | R$ 8,05 M |
| Uplift GMV anual | +R$ 456 k | +R$ 456 k |

*Nota de consistencia:* la base de AOV sale de los primeros pedidos deduplicados y se aplica al
volumen sin deduplicar; como la dedup mueve el AOV solo −0,35 % (auditoría Fase 2 §B3), el sesgo es
despreciable. Se documenta.

### B4. Forest plot de segmentos (§5.4)

Tres niveles recomputados a mano coinciden exactamente con `outputs/tables/fase5_segmentos.csv`
(`cesta:1 item` +6,111 %; `payment_type:credit_card` +6,027 %; `cat_grupo:health_beauty` +12,317 %).

### B5. Decisión (§5.6)

**LANZAR** se mantiene: efecto significativo, IC entero sobre el MDE +3 %, guardrails intactos,
efecto relativo homogéneo, impacto material. Las tres ramas de la regla (NO LANZAR / ITERAR /
LANZAR) siguen siendo alcanzables (Fase 4 §4.5).

---

## C. Puntos menores registrados (sin acción)

1. **`log(AOV)` heterocedástico leve (Levene p = 0,019):** cubierto por el paso a HC3.
2. **Escala mixta winsor/no-winsor:** el forest plot usa `merch_value_w` (Welch, robusto) y los
   tests de interacción usan `log(merch_value)` sin winsorizar. No es inconsistencia — el log ya
   controla la cola; se documenta en el notebook.
3. **`p_value` primario en el JSON:** scipy hace underflow a 0.0; se reporta vía `log10(p) = −10,5`
   (equivale a p ≈ 3·10⁻¹¹, idéntico al valor de la Fase 4).

---

## D. Resolución

- Corrección A aplicada a `src/evaluation.py`; `docs/05_evaluation.md` §5.4 y §5.5 actualizados.
- Sin re-ejecución de otras fases.
- Procede el commit de la corrección y el arranque de la Fase 6.
