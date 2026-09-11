# Auditoría de implementación — ¿hace el código lo que dicen los documentos?

> Cuarta ronda de autocrítica. Complementa las tres auditorías anteriores (`auditoria_fase1_fase2.md`,
> `auditoria_fase5.md`, `auditoria_global.md`), que se centraron en los **números** y las
> **decisiones metodológicas**. Ninguna de las tres comparó, línea a línea, el texto de un `.md` con
> el código que debería producirlo. Esta lo hace: lectura completa de `params.yaml`, `run_all.py`,
> los módulos de `src/` y los tests de `tests/`, contrastando cada afirmación de diseño contra su
> implementación real.
>
> **Veredicto:** el diseño experimental sigue siendo sólido. Se encontraron **dos defectos de
> implementación reales** que las auditorías anteriores no detectaron por no auditar código —
> ninguno cambiaba la decisión final (LANZAR), pero ambos contradecían garantías que el proyecto
> declara explícitamente. Los dos están corregidos, con test de regresión añadido para cada uno.

---

## Hallazgo 1 (severidad alta, corregido) — G2 recalculaba la asignación control/treatment

**Problema.** El diseño exige una asignación control/treatment **única**, calculada una vez por
`customer_unique_id` y persistida en `analytical_table.parquet` (§1.3). `modeling.py ::
g2_cancellation_guardrail()` la recalculaba desde cero con `rng.choice(size=len(o))` sobre una tabla
que **no conserva el mismo orden de filas** que la tabla analítica (G2 no aplica `VALID_STATUS`,
porque necesita conservar los pedidos `canceled`, que es justo lo que mide). Con asignación indexada
por posición y órdenes de fila distintos, el grupo de un mismo cliente en G2 podía no coincidir con
su grupo real.

Con los parámetros actuales no se notaba (ningún efecto se inyecta en guardrails, así que ambos
splits son intercambiables), pero era una inconsistencia interna verificable: la partición
control/treatment no era la misma en todos los puntos del pipeline, contradiciendo §1.3.

**Corrección aplicada.** `g2_cancellation_guardrail()` ahora lee el `group` persistido en
`analytical_table.parquet` y hace `merge` por `customer_unique_id` (como ya hacía correctamente
`clustered_se_robustness()` en el mismo fichero), en vez de reasignar por posición. El `n` de G2 baja
a los clientes presentes en la tabla analítica — correcto, son los únicos a los que el experimento
asignó realmente un grupo.

**Efecto sobre el número reportado — por qué no es una simple recolocación de etiquetas.** La tasa de
cancelación de G2 baja de 0,54 %/0,57 % (versión con bug) a 0,02 %/0,04 % (versión corregida): una
caída de un orden de magnitud, no un simple reetiquetado de grupos. La razón es que el `inner join`
contra `analytical_table.parquet` excluye ahora a los clientes cuyo único pedido en la ventana fue
cancelado — nunca llegaron a tener un pedido válido, así que nunca fueron asignados a un grupo real y
no deberían contar en un guardrail *del experimento*. Antes, el guardrail medía la cancelación sobre
**todo el que compró en la ventana** (una cifra cercana a la tasa global de cancelación de la Fase 2,
0,63 %, `fase2_resumen.json :: tasa_cancelacion_pct_global`); ahora mide la cancelación sobre **quien
quedó efectivamente asignado al experimento**, que por construcción excluye a quien solo canceló. Son
poblaciones distintas por diseño — mezclar en el denominador a gente que el experimento nunca tocó
inflaría artificialmente la tasa base y diluiría cualquier señal real de degradación — y esta es la
definición metodológicamente correcta para un guardrail de experimento, no una inconsistencia entre
la versión antigua y la nueva. Queda documentado en el propio `guardrails_nota` de
`fase4_resumen.json` para que quien compare ambos números tenga el contexto sin tener que leer el
código.

**Test de regresión:** `tests/test_outputs.py :: test_g2_uses_same_assignment_as_analytical_table`
recomputa control/treatment de forma independiente (merge directo cliente→group) y compara contra lo
que devuelve la función real.

---

## Hallazgo 2 (severidad alta, corregido) — la regla de dos puertas no llegaba al código de decisión

**Problema.** La auditoría global (D19) identificó correctamente que a n≈47k/grupo cualquier
regresión mínima en un guardrail sale significativa, y corrigió la regla a "significativo **Y**
magnitud ≥ umbral". Esa corrección se demostró en `guardrail_regression_scenarios()` — una función
aislada, solo ilustrativa. La evaluación real, `run_ab_test()` → `guard[k]["significativo_tras_BH"]`,
y el informe de reproducibilidad de `run_all.py` (`guard_ok = all(not g["significativo_tras_BH"] ...)`),
**nunca aplicaban ningún criterio de magnitud**. La regla "Y" quedaba demostrada en un JSON que nadie
leía para decidir.

**Corrección aplicada.**
- `params.yaml` declara los umbrales de negocio de §1.4 (`guardrail_thresholds`): G1 review_score
  0,05 pts, G2 cancelación 0,2 pp, G3 flete ≥ 20 % del alza de AOV. **G4 (frecuencia) no tiene un
  umbral de magnitud cuantificado en el diseño original** ("magnitud relevante" sin número) — se deja
  explícitamente solo con el criterio de significancia, declarado como limitación conocida en vez de
  inventar un umbral sin base.
- `config.py` expone `GUARDRAIL_THRESHOLDS`, siguiendo la regla de una única fuente de verdad.
- `run_ab_test()` calcula `magnitud_supera_umbral` y `bloquea = significativo_tras_BH AND
  magnitud_supera_umbral` para cada guardrail — este es ahora el campo que debe leer cualquier
  consumidor de la decisión.
- `run_all.py::reproducibility_report()` comprueba `not g["bloquea"]` en vez de
  `not g["significativo_tras_BH"]`.

**Test de regresión:** `test_guardrail_bloquea_is_two_gate_and` verifica que `bloquea` es exactamente
el AND declarado; `test_guardrails_not_degraded` se actualizó para comprobar `bloquea` (el campo que
realmente gobierna la decisión) en vez de la significancia a secas.

---

## Hallazgos medios (corregidos)

- **Balance check por *parsing* de texto crudo** en `run_all.py::reproducibility_report()`
  (`"False" not in bal.split("balanceada")[1]`) — reemplazado por lectura con `pandas` y
  `bal["balanceada"].all()`, idéntico al test equivalente en `test_outputs.py`.
- **Leyenda desactualizada** en `figures_fase2.py` ("log(AOV) ... casi normal"), que no reflejaba la
  matización ya aplicada al texto en `auditoria_fase1_fase2.md` — corregida a "rango robusto para el
  t-test; TCL a n grande".
- **Número mágico `20`** (meses de ventana) hardcodeado en `evaluation.py::main()` para anualizar el
  impacto económico — reemplazado por el mismo cálculo derivado de `WINDOW_START`/`WINDOW_END` que ya
  usaba `tests/test_config.py::test_window_is_20_months` para verificarlo indirectamente.

## Hallazgos de bajo impacto (no corregidos, documentados como limitación conocida)

- Lógica de carga/filtrado de pedidos duplicada en 5-6 puntos de `src/` (causa raíz del hallazgo 1).
  Refactor deseable (`src/data_loading.py::load_orders(...)`) pero no urgente; queda como trabajo
  futuro.
- La mejora "guardrail con efecto inyectado" (D19) solo cubre G1; G2-G4 no tienen una verificación
  equivalente de potencia.
- El modelo de costes (`mde_cost_model.py`) no descuenta flujos futuros — razonable para un modelo
  ya declarado ilustrativo (§1.5).

---

## Verificación

Pipeline completo re-ejecutado con `python run_all.py` tras aplicar los dos fixes de severidad alta:
la decisión sigue siendo **LANZAR**, con el mismo efecto primario (+5,67 %, IC95 [3,99 %, 7,34 %]) y
los 10 checks del informe de reproducibilidad en verde, incluido el nuevo
`guardrails: ninguno bloquea el lanzamiento (regla de dos puertas)`. Suite `pytest` completa (30 tests
rápidos + 3 lentos) en verde, incluidos los 4 tests de regresión añadidos por esta auditoría.
