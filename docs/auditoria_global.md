# Auditoría global del proyecto — revisión como estadístico experto

> Revisión transversal de **todas** las decisiones metodológicas del proyecto: qué se decidió, por
> qué, qué alternativas había, y qué debilidad queda. Complementa las auditorías por fase
> (`auditoria_fase1_fase2.md`, `auditoria_fase5.md`).
>
> **Veredicto global:** el proyecto es **metodológicamente sólido y honesto**. La limitación
> central —el experimento es simulado— está declarada en todas partes. Hay **6 debilidades
> residuales** que un revisor exigente señalaría; ninguna invalida el trabajo, y 4 de ellas son
> intrínsecas a hacer un proyecto de experimentación sobre un dataset sin experimento.

---

## Parte I — Decisiones de diseño (Fase 1)

### D1. Métrica primaria = AOV, no conversión

- **Decisión:** la métrica de éxito es el valor de mercancía por pedido (AOV).
- **Justificación:** el dataset de Olist empieza en el pedido ya realizado — no hay sesiones,
  visitas ni carritos. La conversión (visita→compra) **no es medible** porque no existe la
  población de "no compradores". El AOV sí, y captura directamente el efecto esperado del
  cross-sell.
- **Alternativas descartadas:** (a) simular una capa de tráfico con no-compradores → **rechazada
  por fabricar datos** (prohibido por los estándares del proyecto); (b) usar un dataset con
  conversión real (Criteo Uplift, Hillstrom) → descartado porque su palanca es marketing, no un
  cambio on-site.
- **Debilidad residual:** el proyecto no demuestra la métrica más típica de e-commerce (conversión
  de funnel). Un reclutador que busque exactamente eso lo notará. **Mitigación:** está justificado
  explícitamente y el AOV es una métrica de negocio de primer orden (revenue = AOV × volumen).
- **Verdicto:** correcta. La alternativa honesta era esta o cambiar de dataset.

### D2. AOV = suma de `price`, excluyendo flete

- **Justificación:** el rediseño (cross-sell + barra de envío gratis) mueve la mercancía comprada,
  no el coste de envío. Meter el flete añadiría ruido no relacionado con la palanca. El flete se
  vigila **como guardrail** (G3).
- **Verdicto:** correcta. `payment_value` (que incluye flete y cuotas) se usó solo como chequeo de
  robustez.

### D3. Unidad de aleatorización = cliente; unidad de análisis = 1 pedido/cliente

- **Decisión:** asignar por `customer_unique_id`; quedarse con el **primer** pedido de cada cliente.
- **Justificación:** asignar por cliente evita que dos pedidos de la misma persona caigan en grupos
  distintos (contaminación, viola SUTVA). Deduplicar a 1 pedido/cliente hace **unidad de
  aleatorización = unidad de análisis**, lo que elimina la necesidad de errores estándar por
  clúster. La auditoría de Fase 3 verificó que esto mueve el AOV medio solo **−0,35 %** y se pierde
  el 3,3 % de los pedidos.
- **Alternativa:** conservar todos los pedidos + SE por clúster de cliente. Igualmente válida; se
  eligió la simple porque el coste es trivial y es más fácil de explicar a un stakeholder. Se
  reporta como robustez.
- **Debilidad residual:** "el primer pedido" introduce un sesgo de left-truncation sutil (los
  clientes que ya habían comprado antes de la ventana entran con un pedido que no es su primero
  real). Afecta a ~40 clientes de 94.703 → **despreciable**.
- **Verdicto:** correcta y bien verificada.

### D4. Test bilateral, α = 0,05

- **Justificación:** bilateral porque el rediseño **también podría bajar** el AOV (p. ej. si la
  barra de "envío gratis" hace que el cliente se autolimite al umbral). Ese resultado debe poder
  detectarse formalmente. α = 0,05 es el estándar de industria.
- **Alternativa:** unilateral (más potencia). Rechazada: en experimentación de producto se
  recomienda bilateral salvo justificación fuerte, y aquí no la hay.
- **Verdicto:** correcta y conservadora.

### D5. MDE de relevancia = +3 % relativo

- **Decisión:** el AOV debe subir ≥ +3 % para justificar el coste del rediseño.
- **Justificación declarada:** por debajo de ~+3 % el margen incremental anual no cubre el coste de
  operar un motor de recomendación.
- **Debilidad residual — la más floja del proyecto:** el +3 % es una **regla de negocio asumida,
  no derivada de un modelo de costes real**. En un proyecto real habría que estimar coste de
  ingeniería, coste de mantenimiento del modelo, y el margen por pedido, y despejar el break-even.
  Aquí es un número puesto a mano.
- **Mitigación:** (a) está declarado como asunción; (b) el barrido de decisión de la Fase 4 (§4.5)
  muestra qué pasaría con MDE distintos; (c) el efecto encontrado (+5,7 %) supera el umbral con
  holgura, así que la conclusión no es sensible a mover el MDE entre +3 % y +4 %.
- **Verdicto:** aceptable para un portfolio, pero es el punto que yo reforzaría primero.

### D6. Corrección de multiplicidad: Benjamini-Hochberg sobre guardrails; primario excluido

- **Justificación:** el primario es **un único contraste preespecificado** → no entra en ninguna
  corrección (es la práctica estándar). Sobre la familia de ~4 guardrails + segmentos se controla
  la **tasa de falsos descubrimientos (FDR)** con BH, no el FWER estricto (Bonferroni), porque el
  objetivo es no perder potencia en contrastes secundarios de vigilancia.
- **Alternativa:** Bonferroni. Más conservador; se usó **además** de BH en la demo de p-hacking
  para mostrar el contraste.
- **Verdicto:** correcta. La elección BH vs Bonferroni está justificada por el objetivo (FDR vs
  FWER), que es exactamente el razonamiento que se espera.

### D7. Regla de decisión: IC vs MDE, no solo p-valor

- **Decisión:** LANZAR solo si (p < 0,05) **y** (IC 95 % del lift enteramente por encima de +3 %)
  **y** (ningún guardrail degradado). ITERAR si significativo pero el IC toca el MDE. NO LANZAR en
  otro caso.
- **Justificación:** a n ≈ 47 k/grupo, un efecto trivial también sale "significativo". Anclar la
  decisión en si **todo el intervalo de confianza** supera el umbral de negocio es lo que separa la
  significancia de la relevancia. El uso de la rama ITERAR evita el binario lanzar/no-lanzar.
- **Verdicto:** excelente. Es el corazón del proyecto y está bien planteado. La Fase 4 §4.5 verifica
  que las tres ramas son alcanzables.

### D8. Modelo del efecto sintético: diluido, multiplicativo, respondedores al azar

- **Decisión:** `aov_T = aov_C · (1 + δ_resp + ε)` para el 20 % de tratados que responde;
  δ_resp = 0,25; ATE = +5 %. Respondedores sorteados **independientes del valor del pedido**.
- **Justificación:** la adopción parcial (solo una fracción responde) es realista; un rediseño no
  mueve a todo el mundo. El multiplicativo encaja con un MDE definido en %.
- **Debilidad residual (importante):** dos elecciones del modelo **condicionan resultados**:
  1. **Respondedores al azar** → el efecto es homogéneo por construcción. La conclusión de la Fase 5
     "el efecto no varía por segmento" está en parte **horneada en el diseño**. Un modelo más
     realista de la barra de envío gratis concentraría el efecto en pedidos justo por debajo del
     umbral (efecto heterogéneo real). Se menciona como extensión (§1.7b) pero no se ejecuta.
  2. **Multiplicativo** → genera automáticamente un lift absoluto mayor en cestas grandes, que es
     exactamente el artefacto que la demo de p-hacking (§5.5) explota. Con un efecto aditivo, esa
     demo saldría distinta.
- **Mitigación:** ambas elecciones están **declaradas** y sus consecuencias **analizadas
  explícitamente** (la homogeneidad se contrasta, no se asume; el artefacto multiplicativo se
  explica). El proyecto no esconde que estos resultados dependen del modelo.
- **Verdicto:** defendible y bien documentada, pero es la decisión con más "grados de libertad del
  investigador". La honestidad con que se trata compensa.

---

## Parte II — Datos y preparación (Fases 2–3)

### D9. Estados válidos = {delivered, shipped, invoiced, approved, processing}

- **Justificación:** un pedido pagado es "compra realizada" aunque aún no haya llegado. Se excluyen
  `canceled`, `unavailable`, `created` (no representan compra efectiva).
- **Robustez:** se conserva `is_delivered` para un análisis restringido solo a entregados.
- **Verdicto:** correcta; el análisis de sensibilidad está previsto.

### D10. Ventana temporal 2017-01 → 2018-08

- **Justificación:** 2016 y sept-oct 2018 son residuales (corte de exportación). La auditoría de
  Fase 2 verificó que restringir **no cambia el AOV medio** (137,42 → 137,37) → es un ajuste **por
  realismo** (que la duración se parezca a un experimento), no una corrección de sesgo.
- **Verdicto:** correcta y, sobre todo, **no sobrevendida** (se dice explícitamente que es
  cosmética).

### D11. `log(AOV)` como vía de robustez, no como primario

- **Hallazgo de la auditoría Fase 1-2:** el t-test sobre `log(AOV)` contrasta el **cociente de
  medias geométricas** (≈ mediana), que es **otra pregunta de negocio**, no una versión "con más
  potencia" del AOV. El negocio quiere la media aritmética (revenue = media × volumen).
- **Verdicto:** distinción sutil y correcta. Muchos proyectos de portfolio la confunden.

### D12. Winsorización a p99,5, solo en la columna de contraste

- **Decisión:** `merch_value_w` recorta en p99,5 (473 pedidos, 0,50 %); el AOV **descriptivo** se
  reporta sin winsorizar (R$ 137,42); el test se reporta **con y sin**.
- **Justificación:** la cola pesadísima (máx R$ 13.440 vs mediana R$ 87; curtosis 271) infla la
  varianza y resta potencia. Winsorizar reduce el CV de 1,52 a 1,28. Se hace **solo para el
  contraste** porque winsorizar desplaza la media un −2,4 % y no debe contaminar el descriptivo.
- **Debilidad residual:** el umbral p99,5 es un **grado de libertad del investigador**. Está
  **preespecificado en la auditoría antes de ver resultados** y se reporta también sin winsorizar
  (los dos dan la misma decisión), que es la forma correcta de gestionarlo, pero sigue siendo una
  elección.
- **Verdicto:** bien gestionada. La regla de oro —preespecificar y reportar ambos— se cumple.

### D13. Deduplicación de reseñas por `review_answer_timestamp`

- **Justificación:** 551 pedidos tienen >1 reseña; quedarse con la más reciente por timestamp (no
  por orden de fila del CSV) es el criterio principista. Impacto en la media: nulo (4,087 vs 4,086),
  pero se hace bien igualmente.
- **Verdicto:** correcta, aunque intrascendente.

### D14. Covariate balance check: |SMD| < 0,10 + test ómnibus

- **Justificación:** el umbral |SMD| < 0,10 es el estándar de la literatura (Austin) para
  "balanceado". Se complementa con χ²/Welch ómnibus por covariable.
- **Resultado:** todas las |SMD| ≤ 0,02; ningún ómnibus significativo (p mínimo 0,32).
- **Debilidad menor:** con 6 covariables y 1 asignación, el balance es casi trivialmente bueno
  (aleatorización sobre n ≈ 95 k). El chequeo es correcto pero poco exigente en este contexto. Lo
  que sí aporta es el **chequeo A/A puntual sobre el outcome** (+1,2 %, p = 0,235), que revela el
  desbalance basal de esta semilla concreta.
- **Verdicto:** correcta; la parte informativa es el A/A sobre el outcome, no el SMD de covariables.

---

## Parte III — Diseño estadístico y ejecución (Fase 4)

### D15. Test primario = t de Welch (no Student, no Mann-Whitney, no permutación)

- **Justificación en tres capas:**
  1. El negocio quiere la **media** → descarta Mann-Whitney (dominancia estocástica) y el t sobre
     log (media geométrica) como primarios.
  2. A n ≈ 47 k/grupo, el **TCL** hace que la distribución muestral de la media sea normal pese al
     skew de 9,8 → el t-test es válido. **Verificado empíricamente**: D'Agostino sobre 5.000 medias
     bootstrap da p = 0,83; y el A/A sobre 2.000 particiones da falsos positivos al 5,0 %.
  3. Welch y no Student porque la verificación de supuestos muestra que **bajo H1 las varianzas de
     grupo difieren** (el efecto diluido infla la varianza del treatment; Levene p = 1,6·10⁻⁶).
- **Verdicto:** **ejemplar.** Es el tipo de razonamiento —verificar el supuesto, y que el resultado
  de la verificación *cambie* la elección del test— que distingue un análisis riguroso.

### D16. Power analysis: analítico + simulado

- **Justificación:** el cálculo analítico (`TTestIndPower`) asume efecto uniforme; el simulado
  (1.000 réplicas re-split + re-inyección) captura la varianza real del efecto diluido.
- **Hallazgo:** la penalización de potencia por dilución es **< 1 pp** en todo el rango de n. La
  predicción de la Fase 1 ("el efecto diluido bajará la potencia") era razonable pero **falsa en
  magnitud** — la varianza natural del AOV (CV ≈ 1,5) domina. Y el estimador es **insesgado** (media
  de 1.000 réplicas = 5,00 %).
- **Verdicto:** excelente. Cuantificar una predicción propia y encontrarla equivocada, y decirlo,
  es exactamente lo que se pide.

### D17. A/A con 2.000 particiones + test KS de uniformidad

- **Justificación:** validar empíricamente que el pipeline **no genera falsos positivos** antes de
  introducir ningún efecto. 2.000 (subido desde 1.000 tras ver que la variante winsorizada rozaba
  KS p = 0,044 por azar).
- **Resultado:** falsos positivos 5,0 % [4,0; 5,9] en las 3 métricas; p-valores uniformes (KS ≥ 0,5).
- **Verdicto:** **la pieza más valiosa del proyecto desde el punto de vista de un rol de
  experimentación.** El A/A es la forma correcta de certificar un motor de experimentación nuevo.

### D18. Bootstrap (10.000) del cociente de medias

- **Justificación:** un IC sin supuesto distribucional como robustez del IC de Welch.
- **Verdicto:** correcta; el IC bootstrap [4,05 %; 8,19 %] concuerda con el de Welch.

### D19. Guardrails sin efecto inyectado

- **Decisión:** no se inyecta ningún efecto en G1–G4; salen planos por construcción.
- **Debilidad residual:** esto hace que el hallazgo "ningún guardrail se degrada" sea **trivialmente
  cierto**. El proyecto **no demuestra que los tests de guardrail detectarían una regresión real**
  — solo la calibración A/A lo sugiere indirectamente.
- **Mitigación:** se declara como extensión ("inyectar una regresión sub-umbral en G1 y ver si el
  diseño la caza"). Sería la mejora nº 2 que yo haría.
- **Verdicto:** aceptable pero es una oportunidad perdida de contenido.

### D20. G2 (cancelación) sobre la tabla de pedidos completa

- **Justificación:** la tabla analítica ya filtra estados no válidos, así que la cancelación se
  evalúa sobre `olist_orders` completa, reasignando por cliente con la misma semilla. Test z de
  proporciones (evento raro, 0,6 %).
- **Verdicto:** correcta; es el detalle que un revisor descuidado se salta.

---

## Parte IV — Evaluación (Fase 5)

### D21. ANCOVA / ajuste por covariables con errores HC3

- **Justificación:** regresar el outcome sobre `treatment` + covariables predictoras (nº ítems,
  flete, categoría, región, trimestre) reduce la varianza residual sin sesgar el estimador
  (equivale a CUPED cuando no hay periodo pre). HC3 por la heterocedasticidad.
- **Resultado:** R² = 0,20 → **SE −11,2 %**; el estimador pasa de +5,67 % a +5,19 % (más cerca del
  +5 % real).
- **Matiz honesto (de la auditoría Fase 5):** la reducción de SE es el beneficio **robusto y
  generalizable**; el desplazamiento del punto es en parte específico de esta muestra y **no se
  vende como propiedad general**.
- **Verdicto:** correcta y con el matiz adecuado.

### D22. Segmentos preespecificados (5), no exploratorios

- **Decisión:** `cesta`, `payment_type`, `macro_region`, `trimestre`, `cat_grupo`, declarados
  **antes** de mirar resultados por segmento. Se **descartó** "nuevos vs recurrentes" por
  degenerado (n_recurrente ≈ 40, consecuencia de la dedup) — declarado, no escondido.
- **Verdicto:** correcta. La preespecificación es la defensa nº 1 contra el p-hacking.

### D23. Tests de interacción en escala log (efecto relativo), no en nivel

- **Justificación:** el efecto es multiplicativo → el lift **absoluto** en R$ es mecánicamente
  mayor en cestas grandes. Un test en nivel detectaría "heterogeneidad" que es un artefacto. La
  pregunta de negocio es si el **%** cambia → escala log.
- **Verdicto:** **sutil y correcta.** Este es el tipo de decisión que separa a un analista senior.

### D24. Cambio a Wald HC3 (desde F-test homocedástico) tras la auditoría

- **Motivo:** los tests de interacción usaban el F-test homocedástico, pero bajo H1 hay
  heterocedasticidad (Levene nivel p = 8·10⁻⁸, log p = 0,019). Se pasó a Wald con errores HC3.
- **Impacto:** §5.4 sin cambio de conclusión; §5.5 (p-hacking) **se reforzó** — con SE correctas,
  los artefactos del test en nivel sobreviven a Bonferroni (3 tras BH, 2 tras Bonferroni), y en log
  no sobrevive nada.
- **Verdicto:** la auditoría hizo su trabajo. El resultado corregido es más fuerte, no más débil.

### D25. Demo de p-hacking: 38 cortes, nivel vs log, BH vs Bonferroni

- **Verdicto:** **la pieza más original del proyecto.** Demuestra empíricamente que **corregir por
  multiplicidad no salva un estimando mal planteado**: en la escala equivocada, los falsos hallazgos
  sobreviven incluso a Bonferroni. Poco visto en portfolios.

### D26. Impacto económico: extrapolación lineal + comisión 15 %

- **Debilidades residuales:**
  1. **Extrapolación lineal** del lift por pedido al volumen anual → ignora novedad, saturación,
     estacionalidad, y que el efecto podría no mantenerse fuera de la muestra.
  2. La **comisión del 15 %** es un número **inventado** (Olist no publica su take rate en el
     dataset). Está etiquetado "a efectos ilustrativos".
  3. La base de AOV sale de pedidos deduplicados y se aplica al volumen sin deduplicar (sesgo
     −0,35 %, documentado).
- **Mitigación:** todo declarado; la cifra se presenta como "estimación" con IC, no como
  proyección financiera.
- **Verdicto:** aceptable como orden de magnitud; no es un business case.

---

## Parte V — Debilidades del proyecto (síntesis honesta)

| # | Debilidad | Severidad | ¿Intrínseca? | Estado |
|---|---|---|---|---|
| 1 | **El experimento es simulado** → validez externa nula | Alta (pero es el planteamiento) | Sí | Declarado en cada documento; el proyecto valida el *proceso* |
| 2 | **El modelo del efecto** condiciona la homogeneidad y el artefacto de p-hacking | Media | Parcial | Consecuencias analizadas; **§4.8 añade una variante con efecto heterogéneo real** y muestra que el diseño la detecta |
| 3 | **MDE de relevancia +3 %** asertado | Media | No | **RESUELTO** — `src/mde_cost_model.py` deriva el break-even; el +3 % es válido para volumen ≥ ~415 k pedidos/año (§1.5) |
| 4 | **Un solo split de análisis** (SEED 42) | Baja-Media | No | **RESUELTO** — §4.6 A/B multi-semilla (500): crudo insesgado, cobertura IC 0,94; el split es una realización normal |
| 5 | **Guardrails sin efecto inyectado** → "no degradación" trivial | Media | No | **RESUELTO** — §4.7 inyecta regresiones en G1 y verifica que el diseño caza −0,08 y deja pasar −0,03; **regla de guardrail corregida** a "significativo Y magnitud" |
| 6 | **Sin métrica de retención / LTV** | Baja | Sí (dato) | Recompra 3 % en Olist lo impide; declarado |

**Ninguna es fatal.** Tras las mejoras aplicadas, las únicas que quedan son la nº 1 y la nº 6,
ambas consecuencia inevitable de elegir Olist, y un residuo de la nº 2 (la forma funcional del
efecto sigue siendo una elección declarada). Hallazgo colateral de la mejora nº3 (multi-semilla):
**la winsorización introduce un sesgo negativo de −0,36 pp** en el estimador puntual — se documenta
en §4.6 y se reportan crudo y winsor por separado.

---

## Parte VI — Lo que está hecho especialmente bien

1. **Disciplina de preespecificación.** H0/H1, métrica única, guardrails, MDE y regla de decisión
   escritos **antes** de tocar datos. El notebook y los docs mantienen el orden.
2. **Separar significancia de relevancia** con una regla operativa (IC vs MDE), no un discurso.
3. **Verificación de supuestos que cambia la decisión** (Welch en vez de Student por
   heterocedasticidad bajo H1). No es decorativa.
4. **Calibración A/A** sobre 2.000 particiones — la forma correcta de certificar un pipeline de
   experimentación nuevo.
5. **Cuantificar una predicción propia y refutarla** (la penalización por dilución resultó
   despreciable) y decirlo.
6. **La demo de p-hacking** (estimando correcto vs incorrecto; BH vs Bonferroni).
7. **Trazabilidad y reproducibilidad**: un commit por fase + auditorías; semillas fijas; outputs
   byte-idénticos tras re-ejecución. **Endurecida tras la crítica del usuario**: `params.yaml` como
   única fuente de verdad, `run_all.py` como único entrypoint con informe de reproducibilidad,
   notebook reducido a capa de solo-lectura (sin ruta de ejecución paralela), suite `pytest` con
   un test de idempotencia bit a bit.
8. **Autocrítica documentada**: 3 auditorías (esta incluida) que encontraron y corrigieron cosas
   reales (F-test → HC3; "casi normal" → matizado; SE por clúster → dedup; SEED duplicado →
   `config.py`).

---

## Parte VII — Mejoras aplicadas (todas)

Las 6 mejoras propuestas en la primera versión de esta auditoría **se han implementado** (2ª pasada):

| # | Mejora | Dónde | Resultado |
|---|---|---|---|
| 1 | Regresión inyectada en guardrail G1 + regla de dos puertas | `modeling.py :: guardrail_regression_scenarios` · §4.7 · §1.4 | El test caza −0,08 pts, deja pasar −0,03; regla corregida a "significativo **Y** magnitud" |
| 2 | Variante con efecto heterogéneo real (bajo umbral de envío gratis) | `modeling.py :: heterogeneous_effect_variant` · §4.8 | Interacción detectada (p = 2·10⁻¹⁵); el análisis de segmentos funciona cuando hay algo que encontrar |
| 3 | A/B multi-semilla (500 réplicas), crudo vs winsor | `modeling.py :: ab_multiseed` · §4.6 | Crudo insesgado (−0,03 pp), cobertura 0,94; **winsor con −0,36 pp de sesgo** (hallazgo nuevo) |
| 4 | Modelo de costes para el MDE | `src/mde_cost_model.py` · §1.5 · `f_mde_breakeven.png` | El +3 % es break-even para volumen ≥ ~415 k pedidos/año (payback 2a) |
| 5 | Todos los pedidos + SE por clúster de cliente | `modeling.py :: clustered_se_robustness` · §4.9 | Clustering infla el SE solo 1,1 %; lift +5,71 % vs +5,67 % deduplicado |
| 6 | SRM check formal | `balance_check.py` · §3.5 · `fase3_srm.csv` | χ² = 0,216, p = 0,642 → sin SRM |

---

## Veredicto final

**El proyecto demuestra criterio estadístico de nivel senior en experimentación de producto.** Las
decisiones están justificadas, las alternativas consideradas, y —lo más importante— las debilidades
declaradas en lugar de escondidas. La limitación de fondo (experimento simulado) es inevitable con
un dataset público de e-commerce y está gestionada con honestidad ejemplar: el proyecto no pretende
haber descubierto nada sobre Olist, sino demostrar que sabe **diseñar, ejecutar, auditar y decidir**
un experimento. Para un portfolio dirigido a roles de Product / Data Analyst, cumple con creces.

Las 6 mejoras de la Parte VII se han aplicado en una segunda pasada. Ninguna cambió la decisión
(**LANZAR**); dos aportaron hallazgos nuevos: (a) la regla de guardrail necesitaba dos puertas
("significativo Y magnitud") porque a n grande todo es significativo; (b) la winsorización, elegida
para reducir varianza, introduce un sesgo puntual de −0,36 pp — se reportan crudo y winsor por
separado.
