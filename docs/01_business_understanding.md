# Fase 1 — Comprensión del negocio (Business Understanding)

> CRISP-DM · Fase 1 de 6
> Proyecto: A/B testing en marketplace (dataset Brazilian E-Commerce by Olist)
> Estado: **cerrada** — baseline del AOV fijado en Fase 2; refinada tras la auditoría (ver `docs/auditoria_fase1_fase2.md`).

---

## 1.1 Contexto de negocio

Olist es un **marketplace** brasileño que conecta a pequeños y medianos vendedores con los grandes
canales de venta online del país. El cliente final navega un catálogo, realiza un pedido (que puede
contener productos de varios vendedores) y, tras la entrega, deja una reseña con puntuación de 1 a 5.

El dataset público cubre **~100.000 pedidos realizados entre septiembre de 2016 y octubre de 2018**,
repartidos en 9 tablas relacionales (pedidos, ítems de pedido, pagos, reseñas, clientes, vendedores,
productos, geolocalización y traducción de categorías).

### Palanca de producto evaluada

El equipo de Producto (célula de *Checkout & Conversion*) propone un **rediseño del bloque de
producto** en la ficha de artículo que combina dos elementos:

1. Un módulo de **recomendaciones "productos que suelen comprarse juntos"** (cross-sell) sobre la
   ficha y en el carrito.
2. Una **barra de progreso hacia envío gratuito** que se activa a partir de un umbral de importe.

**Hipótesis de producto:** ambos elementos empujan al cliente a añadir ítems adicionales al pedido,
por lo que se espera un incremento del **valor medio del pedido (Average Order Value, AOV)** sin
deteriorar la satisfacción ni disparar las cancelaciones.

### Por qué un experimento y no un análisis observacional

El cambio afecta al comportamiento de compra de forma potencialmente sutil y está confundido con
estacionalidad, mix de categorías y perfil de cliente. Solo una **asignación aleatoria** permite
atribuir causalmente la diferencia de AOV al rediseño. De ahí el diseño A/B.

---

## 1.2 Limitación estructural del dataset y cómo se acota el alcance

**El dataset de Olist arranca en el pedido ya realizado: no contiene sesiones, visitas ni carritos
abandonados.** En consecuencia:

| Métrica típica de e-commerce | ¿Medible con Olist? | Motivo |
|---|---|---|
| Tasa de conversión visita → pedido | ❌ No | No hay población de "no compradores" |
| Tasa de abandono de carrito | ❌ No | No hay eventos de carrito |
| **Valor medio del pedido (AOV)** | ✅ Sí | `order_items.price` agregado por pedido |
| **Puntuación media de reseña** | ✅ Sí | `order_reviews.review_score` |
| **Tasa de cancelación** | ✅ Sí | `orders.order_status == 'canceled'` |
| Ítems por pedido | ✅ Sí | Conteo de `order_items` por pedido |
| Recompra en ventana | ⚠️ Limitada | `customer_unique_id` permite identificarla, pero la recompra es muy baja (~3 %) |

**Decisión de alcance:** la métrica primaria será el **AOV**, no la conversión. Es la métrica que el
dataset soporta con rigor y la que captura directamente el efecto esperado del cross-sell + envío
gratis. No se simulará una capa de tráfico/no-compradores porque eso implicaría **fabricar datos**,
algo prohibido por los estándares de calidad del proyecto. Sí se inyectará —de forma declarada— un
efecto de tratamiento sobre observaciones reales (ver §1.7).

---

## 1.3 Unidad de aleatorización y de análisis

- **Unidad de aleatorización:** el cliente (`customer_unique_id`). Asignar por cliente y no por
  pedido evita que dos pedidos del mismo cliente caigan en grupos distintos (contaminación) y
  respeta el supuesto SUTVA.
- **Unidad de análisis: el pedido, deduplicado a 1 pedido por cliente** (el primero de la ventana).
  Justificación (auditoría §B3): el 96,96 % de los clientes solo tiene un pedido, y quedarse con el
  primero de cada cliente desplaza el AOV medio solo **−0,35 %** (R$ 137,42 → 137,90). A cambio,
  **unidad de aleatorización = unidad de análisis**, lo que elimina la necesidad de errores estándar
  por clúster y hace el análisis más transparente para un stakeholder. Como robustez se reportará
  también el análisis con **todos los pedidos + SE por clúster de cliente**.
- **Ratio de asignación:** 50 / 50 (máxima potencia para un tamaño total fijo).

---

## 1.4 Hipótesis

### Métrica primaria — AOV

| | Formulación de negocio | Formulación estadística |
|---|---|---|
| **H0** | El rediseño no cambia el valor medio del pedido. | μ_T − μ_C = 0 |
| **H1** | El rediseño cambia el valor medio del pedido. | μ_T − μ_C ≠ 0 |

- **Test bilateral (two-sided), α = 0,05.** Se elige bilateral —y no unilateral— porque un rediseño
  también puede *reducir* el AOV (p. ej. si el foco en "envío gratis" hace que el cliente se
  autolimite al umbral), y ese resultado debe poder detectarse formalmente, no solo vía guardrails.
- μ = media del valor de mercancía por pedido (`sum(order_items.price)` por `order_id`; el flete se
  excluye porque el rediseño no lo mueve — se vigila como guardrail).

### Métricas guardrail (no deben degradarse)

| Guardrail | Definición | Umbral de alarma | Test |
|---|---|---|---|
| G1 — Satisfacción | `review_score` medio (1–5) | Caída ≥ 0,05 pts **o** diferencia significativa a la baja | t-test / Mann–Whitney |
| G2 — Cancelación | % de pedidos con `order_status == 'canceled'` | Subida significativa | Test de proporciones (z) |
| G3 — Flete asumido | `freight_value` medio por pedido | Subida significativa que compense el alza de AOV | t-test |
| G4 — Frecuencia | Pedidos por cliente en la ventana | Caída significativa (que el AOV no suba solo por comprar menos veces) | Test de proporciones / t-test |

Las métricas guardrail se testan con **corrección por comparaciones múltiples** (ver §1.6).

---

## 1.5 Criterio de decisión de negocio (MDE y regla de lanzamiento)

### Efecto mínimo detectable (MDE) de relevancia

La significancia estadística no basta: hay que fijar **qué tamaño de efecto justifica el coste** de
construir y mantener el rediseño (esfuerzo de ingeniería + diseño + mantenimiento del motor de
recomendación).

- El MDE de relevancia se fija **en términos relativos: +3 % sobre el AOV base**.
- Justificación: por debajo de ~+3 % el incremento de margen anual del marketplace no cubre el coste
  incremental de operar un motor de cross-sell (regla de negocio asumida para el proyecto; el valor
  exacto se recalibra en la Fase 5 con el AOV y el volumen reales una vez perfilados en la Fase 2).
- El **cálculo de potencia de la Fase 4** invierte el problema: con el tamaño muestral **fijo** que
  impone el dataset (~95 k clientes), se calculará **qué MDE se puede detectar al 80 % de potencia y
  α = 0,05 bilateral**, y se comparará con el umbral de relevancia de +3 %.
- **Advertencia (auditoría §C):** el preview analítico de la Fase 2 da un efecto detectable de
  ~+2,7 % (datos crudos) o ~+2,3 % (winsorizado p99,5) — por debajo de +3 %, pero con un margen
  estrecho. La conclusión de "muestra suficientemente potente" **no se apoya en ese margen**, sino
  en la **potencia empírica alcanzada al δ inyectado** (§1.7), medida por simulación repetida en la
  Fase 4.
- **Hipótesis a contrastar en la Fase 4:** que el efecto **diluido** (§1.7b) reduzca la potencia
  respecto a un efecto uniforme del mismo tamaño medio. Es una predicción razonable —concentrar el
  efecto en el 20 % infla la varianza del grupo *treatment*—, pero **debe cuantificarse, no
  asumirse**. (Resultado de la Fase 4: la penalización es **despreciable** aquí, porque la varianza
  natural del AOV, CV ≈ 1,5, domina; ver `docs/04_modeling.md` §4.2.)

### Regla de decisión

| Resultado | Decisión de producto |
|---|---|
| Efecto primario significativo (p < 0,05) **e** IC 95 % del *lift* **enteramente por encima** de +3 % **y** ningún guardrail degradado | **Lanzar** |
| Efecto positivo y significativo **pero** el IC 95 % incluye valores por debajo de +3 % | **Iterar** (el efecto es real pero no concluyentemente relevante; refinar diseño o segmento) |
| Efecto no significativo, negativo, o cualquier guardrail degradado de forma significativa | **No lanzar** |

---

## 1.6 Diseño estadístico previsto (se detalla y ejecuta en la Fase 4)

- **Test primario:** **t de Welch sobre el AOV bruto** (media aritmética entre grupos). Es la
  métrica de negocio: revenue = media × volumen. A n ≈ 47–48 k por grupo el Teorema Central del
  Límite hace que la distribución muestral de la media sea normal pese al skew de 9,8, por lo que
  Welch es válido; se confirma empíricamente con el A/A (§1.7a).
- **Robustez, NO sustitutos del primario** (auditoría §B2): (i) t sobre `log(AOV)` — contrasta el
  **cociente de medias geométricas** (≈ mediana), que es *otra* pregunta, no una versión "con más
  potencia" del AOV; (ii) Mann–Whitney — dominancia estocástica; (iii) **bootstrap** de la
  diferencia de medias sin supuesto distribucional; (iv) media winsorizada p99,5. Se reportan todos;
  la decisión de negocio se ancla en Welch sobre el AOV bruto.
- **Corrección por comparaciones múltiples:** **Benjamini–Hochberg (FDR)** sobre la familia de
  guardrails + cualquier análisis por segmentos. Se elige BH sobre Bonferroni porque el objetivo es
  controlar la tasa de falsos descubrimientos manteniendo potencia razonable en un conjunto de
  ~4–8 contrastes secundarios, no el FWER estricto. La métrica primaria **no** entra en la
  corrección (es un único contraste preespecificado).
- **Reporte:** para cada métrica — tamaño del efecto (absoluto y relativo), IC 95 %, p-valor, y n
  por grupo. Nunca solo el p-valor.

---

## 1.7 Diseño de la simulación (declarado y trazable)

Como el dataset no trae grupos, la asignación se **simula**. Se ejecutan **dos experimentos**:

### (a) Test A/A — validación del pipeline y del error de tipo I

- Asignación aleatoria 50/50 por `customer_unique_id`, semilla fija.
- **No se modifica ninguna métrica.**
- Resultados esperados si el pipeline es correcto:
  - Balance de covariables (`customer_state`, categoría dominante del pedido, mes de compra, tipo de
    pago, nº de ítems) **no significativo** (SMD < 0,1 y test ómnibus no significativo).
  - Al repetir el A/A sobre **muchas particiones aleatorias** (p. ej. 1.000 semillas), la tasa de
    rechazo de H0 a α = 0,05 debe rondar el **5 %**, y la distribución de p-valores debe ser
    **uniforme** (test de Kolmogórov–Smirnov contra la uniforme).
- Propósito: demostrar que el diseño **no genera falsos positivos** y que los p-valores están
  calibrados **antes** de introducir ningún efecto.

### (b) Test A/B — efecto de tratamiento sintético **diluido** y declarado

Modelo elegido (auditoría §D, opción b): **adopción parcial**. Un rediseño real solo mueve a una
fracción de los usuarios; el resto no cambia su comportamiento. Para cada pedido del grupo
*treatment* `i`:

```
R_i  ~ Bernoulli(p_resp)                          # ¿responde este usuario al rediseño?
si R_i = 1:  aov_T_i = aov_C_i · (1 + δ_resp + ε_i)
si R_i = 0:  aov_T_i = aov_C_i                     # sin cambio
```

| Parámetro | Valor declarado | Sentido |
|---|---|---|
| `p_resp` | **0,20** | 20 % de los pedidos tratados responden |
| `δ_resp` | **0,25** | los que responden gastan un +25 % |
| `ε_i` | Normal(0; 0,05) | heterogeneidad entre respondedores (no inflar potencia con efecto determinista) |
| **Efecto medio (ATE)** | **`p_resp · δ_resp` = 0,05 → +5 %** | coincide con el δ medio declarado |
| Semilla | fija (`SEED = 42`), documentada en código | reproducibilidad |

- Los respondedores se sortean **al azar, independientes del valor del pedido** (mantiene el ATE
  limpio). Variante opcional para la Fase 5: sesgar los respondedores hacia una banda de importe por
  debajo del umbral de envío gratis (efecto más realista de la barra de progreso).
- El análisis se ejecuta **a ciegas** respecto a `p_resp` y `δ_resp` y debe **recuperar el ATE del
  5 % dentro del IC 95 %**.
- **Predicción a verificar:** al concentrar el efecto en el 20 % de la muestra tratada sube la
  varianza del grupo *treatment*, lo que *podría* reducir la potencia respecto a un efecto uniforme.
  La Fase 4 lo cuantifica por simulación. **Resultado:** el estimador es **insesgado** (media de
  1.000 réplicas = 5,00 %) y la penalización de potencia por dilución es **< 1 pp** en todo el rango
  de n — la intuición es correcta en principio pero **irrelevante en magnitud** aquí. Es un
  hallazgo del proyecto: *verificar* supera a *asumir*.

### Nota de honestidad metodológica (irá también en el README y el notebook)

> El efecto del tratamiento es **conocido por construcción**. El objetivo del proyecto **no** es
> "descubrir" si el rediseño funciona —lo sabemos, porque el efecto lo introducimos nosotros—, sino
> demostrar que **el diseño experimental y el análisis estadístico (a) controlan los falsos
> positivos y (b) recuperan sin sesgo un efecto de tamaño conocido**, con su intervalo de confianza
> y su potencia. Esa es exactamente la competencia que se evalúa en un rol de experimentación de
> producto. Un dataset con aleatorización real (Criteo Uplift, Hillstrom) se descartó porque su
> palanca es un envío de marketing, no un cambio on-site en el marketplace.

---

## 1.8 Control de estacionalidad y ventana temporal

- La asignación es **aleatoria por cliente sobre todo el histórico**, de modo que *treatment* y
  *control* cubren el **mismo rango de fechas** y la estacionalidad queda **balanceada por diseño**.
- La Fase 3 **restringe la ventana** a 2017-01 → 2018-08. Es un ajuste **por realismo** (que la
  duración se parezca a un experimento real y quitar meses residuales), **no una corrección de
  sesgo**: la auditoría (§B6) confirma que el AOV medio apenas se mueve (R$ 137,42 → 137,37) y se
  pierde <1 % de los pedidos.

---

## 1.9 Entregables de la Fase 1

- [x] Problema de negocio definido en términos de producto (rediseño de ficha → AOV).
- [x] H0 / H1 en lenguaje de negocio y estadístico, con métrica primaria única (AOV).
- [x] Métricas guardrail (G1–G4) con umbrales de alarma.
- [x] MDE de relevancia (+3 % relativo) y regla de decisión lanzar / iterar / no lanzar.
- [x] Enfoque de test, corrección por multiplicidad (BH) y diseño de la simulación (A/A + A/B
  diluido, ATE = +5 %).
- [x] Baseline numérico del AOV y su varianza → **cerrado en la Fase 2**: AOV media **R$ 137,42**,
  σ **R$ 209,31**, **CV 1,523**, skew 9,8. `log(AOV)` lleva skew a 0,24 y curtosis a 0,33 (rango
  robusto para t-test; formalmente no normal, pero irrelevante por el TCL a n grande). Preview de
  potencia: efecto detectable ~+2,7 % (crudo) / ~+2,3 % (winsorizado) — la validación real es la
  potencia empírica de la Fase 4.

---

## 1.10 Riesgo de timeline (aviso explícito)

El metaprompt asigna la *Business Understanding* + *Modeling (diseño)* al Bloque 3 (2,5 h, Día 1).
La elección de ejecutar **A/A y A/B** ("Ambos") añade trabajo respecto a solo A/B:

- Coste incremental estimado: **+1 a +1,5 h**, concentrado en la Fase 4 (bucle de 1.000 semillas del
  A/A + test KS de uniformidad de p-valores) y en la Fase 5 (redacción de la validación).
- El grueso del código se **comparte** entre A/A y A/B (misma asignación, mismos tests, mismo power
  analysis), por lo que no se duplica el esfuerzo.
- **Absorción propuesta:** Bloque 6 (Contingencia, 1,5 h, Día 2). Si aun así desborda, el recorte
  sería reducir el bucle A/A de 1.000 a 500 semillas (sigue siendo suficiente para estimar una tasa
  de falsos positivos del ~5 % con precisión aceptable) — **nunca** recortar el power analysis ni la
  verificación de supuestos.
