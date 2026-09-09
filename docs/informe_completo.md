# Informe completo del proyecto
## A/B testing en un marketplace — ¿un rediseño de la ficha de producto aumenta el valor medio del pedido?

> Proyecto de portfolio · metodología **CRISP-DM** · dataset público **Brazilian E-Commerce by Olist**
> Documento de referencia: recorre cada fase, cada decisión metodológica, los resultados (redacción
> tipo TFM) y las limitaciones. Pensado para que alguien que no ha hecho el proyecto entienda
> **qué** se hizo, **cómo** y **por qué**.

---

## Índice

1. [Resumen](#1-resumen)
2. [Introducción](#2-introducción)
3. [Fase 1 — Comprensión del negocio](#3-fase-1--comprensión-del-negocio-business-understanding)
4. [Fase 2 — Comprensión de los datos](#4-fase-2--comprensión-de-los-datos-data-understanding)
5. [Fase 3 — Preparación de los datos](#5-fase-3--preparación-de-los-datos-data-preparation)
6. [Fase 4 — Modelado: diseño estadístico del experimento](#6-fase-4--modelado-diseño-estadístico-del-experimento-modeling)
7. [Fase 5 — Evaluación](#7-fase-5--evaluación-evaluation)
8. [Fase 6 — Despliegue](#8-fase-6--despliegue-deployment)
9. [Resultados](#9-resultados)
10. [Limitaciones](#10-limitaciones)
11. [Discusión y conclusiones](#11-discusión-y-conclusiones)
12. [Trabajo futuro](#12-trabajo-futuro)
13. [Anexos](#13-anexos)

---

## 1. Resumen

Este proyecto reproduce, de principio a fin, el trabajo de un equipo de experimentación de producto
que evalúa un cambio en un marketplace: un **rediseño de la ficha de producto** (recomendaciones de
*cross-sell* y una barra de progreso hacia el envío gratuito) cuya hipótesis es que **incrementa el
valor medio del pedido (AOV)** sin dañar la satisfacción del cliente ni la tasa de cancelación.

El desarrollo sigue las seis fases de **CRISP-DM** y usa el dataset público *Brazilian E-Commerce by
Olist* (~100 000 pedidos, 2017–2018). Como el dataset **no contiene un experimento real**, la
asignación control/tratamiento se **simula** (50/50 por cliente, semilla fija) y el efecto del
rediseño se **inyecta de forma declarada** mediante un modelo *diluido* (el 20 % de los usuarios
tratados responde con un +25 %, para un efecto medio del +5 %). En consecuencia, **el proyecto no
pretende descubrir nada sobre Olist**: demuestra que el **proceso de diseño, análisis y decisión**
es correcto —controla los falsos positivos, recupera sin sesgo un efecto de tamaño conocido, separa
la significancia estadística de la relevancia de negocio y resiste el *p-hacking*—.

**Resultado principal.** El test A/B estima un incremento del AOV de **+5,7 %** (métrica primaria
winsorizada; IC 95 % [+4,0 %; +7,3 %]; p ≈ 3·10⁻¹¹) o **+6,1 %** en la métrica sin winsorizar
(IC 95 % [+4,1 %; +8,1 %]). Ambos intervalos contienen el efecto verdadero inyectado (+5 %) y quedan
**enteramente por encima** del umbral de relevancia de negocio (+3 %). Ningún guardrail se degrada y
el efecto es homogéneo entre segmentos. La regla de decisión devuelve **LANZAR**.

**Hallazgos metodológicos** (subproductos del ejercicio, no de Olist):

- La **heterogeneidad del efecto apenas penaliza la potencia** en este caso (< 0,2 pp): la varianza
  natural del AOV (CV ≈ 1,5) domina la que añade concentrar el efecto en el 20 % de usuarios.
- **Bajo H1 las varianzas de grupo no son iguales** (el efecto multiplicativo infla la varianza del
  *treatment*; Levene p = 1,6·10⁻⁶) → el test primario es la **t de Welch, no la de Student**.
- La **winsorización, elegida para reducir varianza, introduce un sesgo puntual de −0,36 pp** en el
  estimador del lift; se reportan la versión cruda (insesgada) y la winsorizada.
- **A n grande cualquier regresión real es significativa** → la regla de guardrail necesita **dos
  puertas** (significativo **Y** magnitud ≥ umbral), no una.
- **Corregir por comparaciones múltiples no salva un estimando mal planteado**: medir el efecto en
  valor absoluto (R$) sobre cortes correlacionados con el tamaño de cesta fabrica "segmentos
  ganadores" falsos que sobreviven incluso a Bonferroni; en la escala correcta (porcentaje) no
  queda nada.

---

## 2. Introducción

### 2.1 Motivación y objetivo

El objetivo es construir un proyecto de portfolio de **A/B testing en contexto de
e-commerce/marketplace** que refleje el lenguaje y las competencias de las ofertas de Data /
Product Analyst: SQL, Python, diseño experimental, comunicación con *stakeholders* y métricas de
negocio (conversión, retención, *revenue*). El proyecto se diferencia deliberadamente de un
trabajo previo de A/B testing en contexto de gaming, tanto en dominio como en profundidad del
diseño estadístico.

### 2.2 Metodología: CRISP-DM

Todo el desarrollo se organiza en las seis fases de CRISP-DM, sin fusionarlas y manteniendo
trazabilidad:

| Fase | Contenido en este proyecto |
|---|---|
| 1 · Business Understanding | Problema, hipótesis, métrica primaria, guardrails, MDE, regla de decisión, diseño de la simulación |
| 2 · Data Understanding | Procedencia y licencia, perfilado dirigido, limitaciones de validez |
| 3 · Data Preparation | Limpieza dirigida a la pregunta, tabla analítica, asignación simulada, *balance check* |
| 4 · Modeling | Diseño estadístico: *power analysis*, verificación de supuestos, calibración A/A, ejecución del test |
| 5 · Evaluation | Significancia vs. relevancia, impacto económico, análisis por segmentos, decisión |
| 6 · Deployment | Comunicación: resumen ejecutivo, notebook, README, borrador de LinkedIn |

### 2.3 La restricción central: el experimento es simulado

El dataset de Olist **empieza en el pedido ya realizado**: no contiene sesiones, visitas ni
carritos, y por supuesto no contiene un experimento con grupos control y tratamiento. Ante esto se
tomaron dos decisiones que atraviesan todo el proyecto:

1. **La métrica primaria es el AOV**, no la conversión, porque la conversión requeriría una
   población de "no compradores" que el dataset no tiene y que **fabricar sería inaceptable**.
2. **La asignación se simula y el efecto se inyecta de forma declarada.** El parámetro central es
   δ (el efecto medio), fijado en **+5 %**. El análisis se ejecuta "a ciegas" respecto a δ.

El proyecto se lee, por tanto, como una **demostración de método**: sabemos la verdad (la pusimos
nosotros) y comprobamos que la maquinaria estadística la recupera. Esta nota aparece de forma
prominente en todos los entregables.

### 2.4 Cómo está construido el proyecto y cómo se reproduce

- **`params.yaml`** — única fuente de verdad de todos los parámetros (semilla, α, efecto, ventana,
  número de simulaciones, modelo de costes).
- **`src/config.py`** — carga `params.yaml`, añade rutas absolutas y valores derivados. Ningún otro
  módulo define constantes (hay un test que lo verifica).
- **`src/`** — un fichero por fase de CRISP-DM (`profiling_fase2.py`, `figures_fase2.py`,
  `prepare_data.py`, `balance_check.py`, `mde_cost_model.py`, `modeling.py`, `evaluation.py`) más
  `effect_model.py` (el efecto sintético, compartido).
- **`run_all.py`** — único *entrypoint*: ejecuta las seis fases en orden, verifica que cada una
  genera sus salidas y termina con un **informe de reproducibilidad** que comprueba 10 invariantes
  (decisión == LANZAR, tasa de falsos positivos del A/A en [3,5 %; 6,5 %], IC del A/B por encima del
  MDE, sin SRM, guardrails intactos…). Sale con código ≠ 0 si algo falla. ~2 min.
- **`notebooks/ab_test_olist.ipynb`** — capa de **presentación**: solo lee `outputs/` y muestra
  figuras y narrativa; no calcula nada.
- **`tests/`** — `pytest` (rápidos) + `pytest -m slow` (re-ejecuta y comprueba idempotencia bit a
  bit).

```bash
pip install -r requirements.txt
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
python run_all.py     # ~2 min
pytest
```

Todas las semillas están fijadas → el resultado es determinista.

---

## 3. Fase 1 — Comprensión del negocio (Business Understanding)

> Documento fuente: `docs/01_business_understanding.md`. Todas las decisiones de esta fase se toman
> **antes de mirar los datos**.

### 3.1 Contexto de negocio

Olist es un marketplace que conecta a pequeños y medianos vendedores brasileños con los grandes
canales de venta online. El cliente realiza un pedido —que puede contener productos de varios
vendedores— y, tras la entrega, deja una reseña de 1 a 5. El dataset cubre ~100 000 pedidos entre
2016 y 2018, en 9 tablas relacionales.

### 3.2 La palanca de producto evaluada

El equipo de Producto (célula de *Checkout & Conversion*) propone un **rediseño de la ficha de
producto** que combina:

1. Un módulo de **recomendaciones "productos que suelen comprarse juntos"** (*cross-sell*) en la
   ficha y en el carrito.
2. Una **barra de progreso hacia el envío gratuito**, que se activa a partir de un umbral de importe.

**Hipótesis de producto:** ambos elementos empujan al cliente a añadir artículos, por lo que se
espera un **incremento del AOV** sin deterioro de la satisfacción ni de las cancelaciones.

### 3.3 Decisión D1 — Métrica primaria = AOV, no conversión

| | |
|---|---|
| **Decisión** | La métrica de éxito es el **valor de mercancía por pedido** (AOV) = Σ `order_items.price` por `order_id`, excluyendo el flete. |
| **Justificación** | El dataset arranca en el pedido: no hay tráfico ni "no compradores", así que la conversión no es medible con rigor. El AOV sí lo es y captura directamente el efecto esperado del cross-sell. Además, *revenue* = AOV × volumen, así que es una métrica de negocio de primer orden. |
| **Alternativas descartadas** | (a) Simular una capa de tráfico con no-compradores → rechazada por **fabricar datos**. (b) Cambiar a un dataset con conversión real (Criteo Uplift, Hillstrom) → descartada porque su palanca es un envío de marketing, no un cambio *on-site* en el marketplace. |
| **Coste** | El proyecto no demuestra la métrica de funnel más típica de e-commerce. Se asume explícitamente. |

Se excluye el flete de la métrica porque el rediseño no lo mueve; se vigila **como guardrail** (G3).

### 3.4 Decisión D2 — Unidad de aleatorización = cliente; de análisis = 1 pedido/cliente

| | |
|---|---|
| **Decisión** | Aleatorizar por `customer_unique_id`; en el análisis principal quedarse con el **primer pedido de cada cliente**. |
| **Justificación** | Aleatorizar por cliente evita que dos pedidos de la misma persona caigan en grupos distintos (contaminación; violaría SUTVA). Deduplicar a un pedido por cliente hace **unidad de aleatorización = unidad de análisis**, lo que elimina la necesidad de errores estándar por clúster. La Fase 3 verifica que el coste es marginal (el AOV medio se mueve −0,35 %; se pierde el 3,3 % de los pedidos). |
| **Alternativa** | Conservar todos los pedidos + SE por clúster de cliente. Igualmente válida; se elige la simple y se reporta la otra como robustez (Fase 4, §6.8). |
| **Ratio** | 50/50 (máxima potencia para un tamaño total fijo). |

### 3.5 Decisión D3 — Hipótesis, test bilateral, α = 0,05

| | Formulación de negocio | Formulación estadística |
|---|---|---|
| **H0** | El rediseño no cambia el AOV medio | μ_T − μ_C = 0 |
| **H1** | El rediseño cambia el AOV medio | μ_T − μ_C ≠ 0 |

Se elige **bilateral** —y no unilateral, que daría más potencia— porque el rediseño *también podría
bajar* el AOV (p. ej. si el foco en "envío gratis" hace que el cliente se autolimite al umbral), y
ese resultado debe poder detectarse formalmente. α = 0,05 es el estándar de industria.

### 3.6 Decisión D4 — Guardrails y la regla de dos puertas

Métricas de control que **no deben degradarse**:

| Guardrail | Definición | Umbral de alarma |
|---|---|---|
| **G1** — Satisfacción | `review_score` medio (1–5) | Caída significativa **Y** magnitud ≥ 0,05 pts |
| **G2** — Cancelación | % de pedidos `order_status == 'canceled'` | Subida significativa **Y** magnitud relevante |
| **G3** — Flete asumido | `freight_value` medio por pedido | Subida significativa que absorba parte del alza de AOV |
| **G4** — Frecuencia | Nº de ítems por pedido / pedidos por cliente | Caída significativa |

**Regla de dos puertas.** A n ≈ 47 000 por grupo, *cualquier* regresión real es estadísticamente
significativa (la Fase 4, §6.8, muestra que una caída de −0,03 pts en `review_score` da p ≈ 0,001).
Una regla del tipo "significativo **O** magnitud" bloquearía el lanzamiento por ruido sub-umbral.
Se exige por tanto **significativo Y magnitud ≥ umbral**.

La familia de guardrails se testa con **corrección de Benjamini–Hochberg (FDR)**, no Bonferroni: el
objetivo es controlar la tasa de falsos descubrimientos manteniendo potencia en un conjunto de
contrastes de vigilancia, no el FWER estricto. La métrica primaria, al ser un único contraste
preespecificado, **no entra** en la corrección.

### 3.7 Decisión D5 — MDE de relevancia = +3 %, derivado de un modelo de costes

La significancia estadística no basta: hay que fijar **qué tamaño de efecto justifica el coste** de
construir y mantener el rediseño. El *minimum detectable effect* de relevancia se fija en **+3 %
relativo sobre el AOV base** y se **deriva** (no se aserta) de un modelo de *break-even*
(`src/mde_cost_model.py`):

```
lift_breakeven = coste_total / (AOV · volumen_pedidos · comisión · margen · años)
```

Con asunciones ilustrativas (AOV R$ 137, comisión 15 %, margen neto sobre comisión 80 %, construir
R$ 250 000, mantener R$ 80 000/año, horizonte 2 años), el *break-even* **cae con el volumen de
pedidos**:

| Pedidos/año | *Break-even* (payback 2 años) |
|---:|---:|
| 58 700 (el propio dataset) | **+21,2 %** |
| 250 000 | +5,0 % |
| 1 000 000 | +1,25 % |
| 5 000 000 | +0,25 % |

Conclusión: el **+3 % es válido para un marketplace con ≥ ~415 000 pedidos/año**. El proyecto asume
esa escala (marketplace de tamaño medio-grande). Figura: `outputs/figures/f_mde_breakeven.png`.

### 3.8 Decisión D6 — Regla de decisión de producto

| Resultado | Decisión |
|---|---|
| Efecto primario significativo (p < 0,05) **e** IC 95 % del *lift* **enteramente por encima** de +3 % **y** ningún guardrail degradado | **LANZAR** |
| Efecto positivo y significativo **pero** el IC 95 % incluye valores por debajo de +3 % | **ITERAR** (el efecto es real pero no concluyentemente relevante) |
| Efecto no significativo, negativo, o cualquier guardrail degradado | **NO LANZAR** |

La rama **ITERAR** evita el binario lanzar/no-lanzar y ancla la decisión en el **intervalo de
confianza** frente al umbral de negocio, no en el estimador puntual.

### 3.9 Decisión D7 — Diseño de la simulación: A/A + A/B con efecto diluido

Se ejecutan **dos experimentos**:

**(a) Test A/A** — asignación aleatoria 50/50, **sin modificar ninguna métrica**. Propósito:
demostrar empíricamente que el pipeline **no genera falsos positivos** antes de introducir ningún
efecto. Se repite sobre **2 000 particiones aleatorias**: la tasa de rechazo de H0 a α = 0,05 debe
rondar el 5 % y la distribución de p-valores debe ser uniforme (test de Kolmogórov–Smirnov).

**(b) Test A/B — efecto de tratamiento sintético diluido.** Modelo de **adopción parcial**: para
cada pedido del grupo *treatment* `i`:

```
R_i  ~ Bernoulli(p_resp = 0,20)
si R_i = 1:  aov_T_i = aov_C_i · (1 + δ_resp + ε_i),   δ_resp = 0,25,  ε_i ~ N(0; 0,05)
si R_i = 0:  aov_T_i = aov_C_i   (sin cambio)
```

| Parámetro | Valor | Sentido |
|---|---|---|
| `p_resp` | 0,20 | el 20 % de los tratados responde |
| `δ_resp` | 0,25 | los que responden gastan un +25 % |
| **ATE** (efecto medio) | **`p_resp · δ_resp` = 0,05 → +5 %** | coincide con el δ declarado |
| Semilla | `SEED = 42` | reproducibilidad |

Los respondedores se sortean **al azar, independientes del valor del pedido** (mantiene el ATE
limpio). Se eligió el modelo diluido (frente a un multiplicativo uniforme) porque **es más
realista**: un rediseño solo mueve a una fracción de los usuarios.

---

## 4. Fase 2 — Comprensión de los datos (Data Understanding)

> Documento fuente: `docs/02_data_understanding.md`. Script: `src/profiling_fase2.py`.

### 4.1 Procedencia, licencia y estructura

| | |
|---|---|
| Fuente | *Brazilian E-Commerce Public Dataset by Olist* — Kaggle (`olistbr/brazilian-ecommerce`) |
| Licencia | **CC BY-NC-SA 4.0** (verificada en la descarga). Uso no comercial; los CSV crudos **no se versionan** en el repositorio. |
| Tamaño | 9 CSV relacionales, ~42 MB comprimido; **99 441 pedidos** |

Tablas y volúmenes:

| Tabla | Filas | Uso en el experimento |
|---|---:|---|
| `olist_orders_dataset` | 99 441 | espina dorsal: estado, timestamps |
| `olist_order_items_dataset` | 112 650 | **métrica primaria** (`price`, `freight_value`) |
| `olist_order_payments_dataset` | 103 886 | tipo de pago; robustez de importe |
| `olist_order_reviews_dataset` | 99 224 | **guardrail G1** (`review_score`) |
| `olist_customers_dataset` | 99 441 | **unidad de aleatorización** (`customer_unique_id`) |
| `olist_products_dataset` | 32 951 | categoría (segmentación) |
| `olist_sellers`, `olist_geolocation`, `product_category_name_translation` | — | contexto / traducción; geolocalización no se usa |

### 4.2 Decisión D8 — Ventana temporal 2017-01 → 2018-08

El rango bruto es 2016-09 a 2018-10, pero 2016 es testimonial (2016-11 está vacío) y sept-oct 2018
tienen pocos pedidos (corte de exportación). Se restringe a la **ventana estable 2017-01 → 2018-08**.
La Fase 3 verifica que esto **no cambia el AOV medio** (R$ 137,42 → R$ 137,37) ni introduce sesgo:
es un ajuste **por realismo** (que la duración se parezca a un experimento), no correctivo. Figura:
`f2_01_volumen_mensual.png`.

### 4.3 Perfilado de la métrica primaria (AOV)

Pedidos válidos (estado en {delivered, shipped, invoiced, approved, processing} y con al menos un
ítem): **n = 98 199 pedidos / 94 983 clientes únicos**.

| Estadístico | `merch_value` (AOV) | `log(AOV)` |
|---|---:|---:|
| media | **R$ 137,42** | 4,44 |
| mediana | R$ 86,90 | — |
| desv. típica | R$ 209,31 | 0,93 |
| **CV (σ/μ)** | **1,523** | 0,21 |
| p99 / máx | R$ 995 / R$ 13 440 | — |
| **skew** | **9,77** | **0,24** |
| curtosis (exceso) | 271,4 | 0,34 |

**Lecturas clave** (condicionan la Fase 4):

1. El AOV bruto es **extremadamente asimétrico y leptocúrtico** (cola hasta R$ 13 440 frente a
   mediana R$ 87). Figura: `f2_02_distribucion_aov.png`.
2. La transformación logarítmica lleva la asimetría y la curtosis a un **rango robusto** (skew 0,24;
   curtosis 0,34). Formalmente sigue sin ser normal (D'Agostino p < 10⁻²⁰ a n = 5 000), pero eso
   es irrelevante: con n grande la **media** es normal por el Teorema Central del Límite.
3. El t-test sobre `log(AOV)` contrasta el **cociente de medias geométricas** (≈ mediana), que es
   *otra* pregunta de negocio, no el AOV. Entra como **robustez**, no como primario.

### 4.4 Perfilado de los guardrails

| Guardrail | Valor base | Notas |
|---|---|---|
| G1 · `review_score` | media **4,12** / 5 · σ 1,32 · **cobertura 99,3 %** | Distribución en U invertida (58 % son 5★, 11 % son 1★) → no normal |
| G2 · tasa de cancelación | **0,63 %** global | Evento raro → test de proporciones (z); baja potencia |
| G3 · `freight_value` | media **R$ 22,82** / pedido | Vigilar que un alza de AOV no venga con más flete asumido |

### 4.5 Unidad de aleatorización caracterizada

| | |
|---|---:|
| Clientes únicos (válidos) | 94 983 |
| Con exactamente 1 pedido | **96,96 %** |
| % de pedidos de clientes recurrentes | 6,21 % |
| Máx. pedidos de un cliente | 16 |

→ Aleatorizar por `customer_unique_id` es **casi equivalente** a aleatorizar por pedido; deduplicar
a un pedido por cliente es una simplificación de coste marginal.

### 4.6 Calidad de los datos (tratada en la Fase 3)

- 775 pedidos sin ítems (mayoría `unavailable` / `canceled`) → excluidos de la métrica primaria.
- 814 `review_id` duplicados; 551 pedidos con >1 reseña → se conserva la de `review_answer_timestamp`
  más reciente.
- 1 pedido válido sin registro de pago (irrelevante para la métrica primaria).
- Outliers de cola del AOV → winsorización declarada (§5.4).

### 4.7 Limitaciones de validez identificadas

1. **No hay aleatorización real ni capa de tráfico** → no se mide conversión; el efecto se simula.
2. **Efecto de tratamiento no observado en covariables:** al simular, el rediseño solo puede actuar
   sobre la métrica que perturbamos; en la realidad afectaría también al mix de categorías, la tasa
   de devolución, etc.
3. **Ventana histórica de 2 años**, no un experimento de 2–4 semanas (se mitiga restringiendo la
   ventana y balanceando la estacionalidad por diseño).
4. **Recompra muy baja (~3 % de clientes)** → sin métrica primaria de retención posible.
5. **Sesgo de supervivencia** en las reseñas (autoselección del cliente).
6. **Mercado único** (Brasil, 2017–2018) → sin validez externa fuera de ese contexto.

---

## 5. Fase 3 — Preparación de los datos (Data Preparation)

> Documento fuente: `docs/03_data_preparation.md`. Scripts: `src/prepare_data.py`,
> `src/balance_check.py`. Limpieza **dirigida a la pregunta experimental**, no EDA genérica.

### 5.1 Cadena de transformaciones (trazada en `fase3_transformaciones.csv`)

| Paso | n antes | n después | Δ | Justificación |
|---|---:|---:|---:|---|
| Crudo (`olist_orders`) | 99 441 | 99 441 | — | — |
| **Ventana temporal** [2017-01-01, 2018-09-01) | 99 441 | 99 092 | −349 | Elimina el arranque residual y la cola incompleta (ajuste por realismo, no correctivo). |
| **Estados válidos** {delivered, shipped, invoiced, approved, processing} | 99 092 | 97 905 | −1 187 | Un pedido pagado es "compra realizada"; se excluyen `canceled` / `unavailable` / `created`. |
| **Pedidos con ítems** | 97 905 | 97 905 | 0 | Los pedidos sin líneas ya cayeron con los estados no válidos. |
| **Dedup a 1 pedido/cliente** (el primero) | 97 905 | **94 703** | −3 202 | Unidad de aleatorización = unidad de análisis. |

**Tabla analítica final: 94 703 filas × 15 columnas** (`data/processed/analytical_table.parquet`),
grano = 1 pedido-cliente.

### 5.2 Enriquecimiento (variables construidas)

| Columna | Construcción | Uso |
|---|---|---|
| `merch_value` | Σ `order_items.price` por pedido | **métrica primaria** (descriptivos) |
| `merch_value_w` | `merch_value` recortado en **p99,5** | **métrica primaria para el contraste** |
| `freight_value` · `n_items` | Σ / conteo por pedido | guardrails G3, G4 / covariable |
| `review_score` | reseña de timestamp más reciente | guardrail G1 |
| `cat_dominante` | categoría (EN) del ítem más caro | covariable / segmentación |
| `payment_type` | tipo de la fila de mayor `payment_value` | covariable / segmentación |
| `customer_state`, `mes_compra` | de `olist_customers` / truncado a mes | covariables de balance |
| `is_delivered` | `order_status == 'delivered'` | análisis de sensibilidad |
| `group` | ver §5.6 | brazo del experimento |

`review_score` tiene 696 nulos (0,73 %) → análisis de casos completos para G1; el sesgo potencial
es despreciable a ese porcentaje.

### 5.3 El *gotcha* de Olist — resuelto explícitamente

`orders.customer_id` es **único por pedido** (99 441 valores para 99 441 filas); la persona real es
`customers.customer_unique_id` (96 096 valores distintos). Todo el pipeline —dedup, asignación,
conteo de clientes— usa `customer_unique_id`. Es el error más común al trabajar con este dataset y
está verificado en la auditoría.

### 5.4 Decisión D9 — Winsorización a p99,5, solo para el contraste

| | |
|---|---|
| **Decisión** | `merch_value_w` recorta el AOV en el percentil 99,5 (cap ≈ R$ 1 360; **473 pedidos, 0,50 %**). El AOV descriptivo se reporta **sin winsorizar** (R$ 137,42). El test se reporta **con y sin**. |
| **Justificación** | La cola pesadísima (máx R$ 13 440; curtosis 271) infla la varianza y resta potencia. Winsorizar reduce el CV de 1,52 a 1,28. Se hace **solo para el contraste** porque winsorizar desplaza la media un −2,4 % y no debe contaminar el descriptivo. |
| **Cómo se gestiona el grado de libertad** | El umbral p99,5 está **preespecificado en la auditoría antes de ver resultados** y se reporta también la versión sin winsorizar (ambas dan la misma decisión). La Fase 4 (§6.8) descubre que la winsorización introduce un **sesgo de −0,36 pp** en el estimador → se reportan las dos. |

### 5.5 Decisión — Dedup de reseñas por `review_answer_timestamp`

551 pedidos tienen >1 reseña. Deduplicar "por última fila del CSV" vs. "por timestamp más reciente"
cambia el score en 100 pedidos, con impacto nulo en la media (4,087 vs 4,086). Aun así se deduplica
**por timestamp** (criterio principista).

### 5.6 Asignación aleatoria simulada

- **Mecanismo:** `numpy.random.default_rng(SEED=42).choice(["control", "treatment"])` por fila.
- **Resultado:** control = **47 280** · treatment = **47 423** (50,08 % *treatment* — desviación
  esperada del 50 % por azar).
- **El efecto de tratamiento NO se inyecta en esta fase.** La tabla sale con la métrica intacta.

### 5.7 *Covariate balance check* + SRM (`src/balance_check.py`)

Criterio: **|SMD| < 0,10** por covariable y **test ómnibus no significativo**.

| Covariable | SMD | Test | p-valor |
|---|---:|---|---:|
| `n_items` | −0,004 | Welch-t | 0,579 |
| `freight_value` | 0,007 | Welch-t | 0,305 |
| `customer_state` (27) | 0,013 | χ² (dof 26) | 0,919 |
| `cat_dominante` (72) | 0,020 | χ² (dof 71) | 0,320 |
| `payment_type` (4) | 0,009 | χ² (dof 3) | 0,623 |
| `mes_compra` (20) | 0,015 | χ² (dof 19) | 0,693 |

**Todas las |SMD| ≤ 0,02** y **ningún ómnibus significativo** (p mínimo 0,32). Figura:
`f3_01_balance.png` (love-plot).

**SRM check (Sample Ratio Mismatch).** χ² del reparto observado (47 280 / 47 423) frente a 50/50:
**χ² = 0,216; p = 0,642** → el reparto es compatible con 50/50, sin indicio de fuga diferencial de
unidades.

**Chequeo A/A puntual sobre el *outcome*.** Con la semilla declarada, el AOV medio difiere +1,2 %
entre grupos (Welch-t p = 0,235) — **ruido de muestreo**. Es un recordatorio de que una diferencia
bruta del ~1 % entre dos grupos aleatorios es normal, y de que la decisión debe apoyarse en el test
y en el IC, no en el ojo. Este desbalance basal de la semilla 42 se propaga al estimador puntual del
A/B (ver §9).

---

## 6. Fase 4 — Modelado: diseño estadístico del experimento (Modeling)

> Documento fuente: `docs/04_modeling.md`. Script: `src/modeling.py` (600 líneas, 9 bloques).
> En CRISP-DM, "Modeling" aquí = **diseñar y ejecutar el contraste estadístico**.

### 6.1 Power analysis a priori

Con n ≈ 47 000 por grupo, α = 0,05 bilateral, potencia objetivo 0,80:

| Métrica | media | CV | **MDE detectable** |
|---|---:|---:|---:|
| AOV crudo | R$ 137,85 | 1,531 | **+2,79 %** |
| AOV winsorizado p99,5 | R$ 134,49 | 1,282 | **+2,34 %** |

Ambos por debajo del MDE de relevancia (+3 %). La potencia para el efecto declarado (+5 %) es
**≈ 100 %** en las dos métricas, y el estimador es **insesgado** (media de 1 000 réplicas simuladas:
4,999 % en crudo, 5,006 % en winsor).

### 6.2 ¿Penaliza la potencia el efecto diluido? (hallazgo)

Predicción de la Fase 1: concentrar el efecto en el 20 % de los usuarios infla la varianza del
*treatment* y podría bajar la potencia. **Verificado por simulación:** la penalización es **< 0,2 pp**
al n del experimento y **< 1 pp** en toda la rejilla de n probada (400 → 47 000 por grupo). Motivo:
la varianza que añade la dilución (≈ 1,4 % de la varianza total) es minúscula frente a la varianza
natural del AOV (CV ≈ 1,5). **La intuición es correcta en dirección pero irrelevante en magnitud.**
Figura: `f4_04_power_vs_n.png`.

### 6.3 Verificación de supuestos → Welch, no Student

| Supuesto | Prueba | Resultado | Veredicto |
|---|---|---|---|
| Normalidad de los **datos** | D'Agostino K² | K² = 5 453; p ≈ 0 | **No normal** (esperado) |
| Normalidad de la **media** (TCL) | D'Agostino sobre 5 000 medias bootstrap | K² = 0,38; **p = 0,826** | **Compatible con normal → t válida** |
| Homocedasticidad **sin efecto** (A/A) | Levene (centrado en mediana) | stat = 1,61; p = 0,205 | Varianzas iguales (esperado) |
| Homocedasticidad **con efecto diluido** | Levene | stat = 22,97; **p = 1,6·10⁻⁶** | Varianzas **desiguales** bajo H1 → **usar Welch, NO Student** |
| Independencia | por diseño | asignación aleatoria + dedup a 1 pedido/cliente | Sin correlación intra-cliente; SUTVA asumido |

El test primario es la **t de Welch**: la verificación muestra que bajo H1 las varianzas de grupo no
son iguales, exactamente el caso para el que Welch está diseñado. Figura: `f4_01_tcl_normalidad.png`.

### 6.4 Calibración A/A — 2 000 particiones aleatorias

Para cada una de 2 000 particiones 50/50 (sin efecto), Welch-t sobre la métrica y registro del
p-valor. Criterio: IC 95 % de la tasa de falsos positivos que contenga 0,05 **y** p-valores
uniformes (Kolmogórov–Smirnov).

| Métrica | Falsos positivos (α = 0,05) | IC 95 % | KS vs. uniforme (p) | Veredicto |
|---|---:|---:|---:|:--:|
| AOV crudo | **4,95 %** | [3,99 %; 5,91 %] | 0,53 | ✅ calibrado |
| AOV winsor p99,5 | **5,00 %** | [4,04 %; 5,96 %] | 0,93 | ✅ calibrado |
| log(AOV) | **5,00 %** | [4,04 %; 5,96 %] | 0,72 | ✅ calibrado |

Figura: `f4_02_aa_pvalores.png` (histograma plano de p-valores). **El pipeline no genera falsos
positivos y los p-valores están calibrados.**

### 6.5 Test A/B — efecto diluido inyectado (SEED = 42)

| Test | lift AOV | IC 95 % | p-valor |
|---|---:|---:|---:|
| **Welch · AOV crudo** | **+6,11 %** | [+4,09 %; +8,13 %] | 3,1·10⁻⁹ |
| **Welch · AOV winsor p99,5** | **+5,67 %** | [+3,99 %; +7,34 %] | 3,1·10⁻¹¹ |
| Bootstrap (10 000, sin supuestos) | — | [+4,05 %; +8,19 %] | — |
| log · cociente de medias geométricas | +4,79 % | — | 1,4·10⁻¹⁴ |
| Mann–Whitney (dominancia estocástica) | — | — | 1,8·10⁻¹⁵ |

**Todos los intervalos contienen el efecto verdadero (+5 %).** El estimador puntual queda por encima
del 5 % porque este *split* concreto tiene el +1,2 % de desbalance basal descrito en §5.7. Figura:
`f4_03_ab_efecto.png`.

### 6.6 Guardrails (Benjamini–Hochberg, sin efecto inyectado)

| Guardrail | control | treatment | p bruto | **p ajustado (BH)** | ¿Degradado? |
|---|---:|---:|---:|---:|:--:|
| G1 · review_score | 4,114 | 4,116 | 0,80 | 0,80 | ❌ no |
| G2 · tasa de cancelación | 0,541 % | 0,570 % | 0,56 | 0,77 | ❌ no |
| G3 · freight_value | R$ 22,74 | R$ 22,89 | 0,30 | 0,77 | ❌ no |
| G4 · nº de ítems | 1,140 | 1,138 | 0,58 | 0,77 | ❌ no |

**Ningún guardrail se degrada.** Es el resultado esperado: el diseño solo inyecta efecto en la
métrica primaria. La capacidad real de los tests de guardrail para **cazar** una regresión se
verifica aparte (§6.8).

### 6.7 Barrido de decisión — las tres ramas de la regla

Aplicando la regla LANZAR / ITERAR / NO LANZAR a distintos tamaños de efecto inyectado (métrica
primaria winsorizada; guardrails OK; este *split* tiene +1,2 % de desbalance basal):

| ATE inyectado | lift observado | IC 95 % | p-valor | **Decisión** |
|---:|---:|---:|---:|:--:|
| 0 % | +1,01 % | [−0,63 %; +2,65 %] | 0,227 | **NO LANZAR** |
| 1 % | +1,95 % | [+0,30 %; +3,60 %] | 0,020 | **ITERAR** |
| 2 % | +2,89 % | [+1,23 %; +4,54 %] | 6·10⁻⁴ | **ITERAR** |
| 3 % | +3,82 % | [+2,16 %; +5,48 %] | 6·10⁻⁶ | **ITERAR** |
| 4 % | +4,75 % | [+3,08 %; +6,41 %] | 2·10⁻⁸ | **LANZAR** |
| **5 % (declarado)** | **+5,67 %** | **[+3,99 %; +7,34 %]** | **3·10⁻¹¹** | **LANZAR** |
| 8 % | +8,40 % | [+6,71 %; +10,09 %] | 2·10⁻²² | **LANZAR** |

El diseño **alcanza las tres decisiones**.

### 6.8 Robustez adicional

**A/B multi-semilla (500 réplicas).** Se repite el A/B completo (re-*split* + re-inyección) sobre
500 semillas, en crudo y en winsorizado:

| | lift medio | sesgo | p2,5–p97,5 | cobertura IC 95 % del +5 % real |
|---|---:|---:|---:|---:|
| AOV crudo | +4,97 % | **−0,03 pp** | [+2,9 %; +7,1 %] | **0,94** |
| AOV winsor p99,5 | +4,64 % | **−0,36 pp** | [+2,9 %; +6,2 %] | **0,92** |

En crudo el estimador es **insesgado** y el IC tiene cobertura nominal. La winsorización introduce
un **sesgo negativo pequeño** (recorta más los valores altos del *treatment*, que crecieron por el
efecto multiplicativo) a cambio de menor varianza; su IC infra-cubre ligeramente. El +5,7 % del
*split* SEED = 42 está dentro del rango p2,5–p97,5 → es una realización normal.

**Regresión inyectada en un guardrail.** Se inyecta una caída aditiva en `review_score` solo en el
*treatment* y se aplica la regla de dos puertas:

| Regresión inyectada | diff observada | p-valor | ¿Sig.? | ¿Magnitud ≥ 0,05? | Regla "O" | **Regla "Y"** |
|---:|---:|---:|:--:|:--:|:--:|:--:|
| 0,00 | +0,002 | 0,80 | ❌ | ❌ | no bloquea | **no bloquea** ✅ |
| −0,03 | −0,028 | 0,001 | ✅ | ❌ | bloquea (falso) | **no bloquea** ✅ |
| −0,05 | −0,048 | 3·10⁻⁸ | ✅ | ❌ (justo por debajo) | bloquea | no bloquea (límite) |
| −0,08 | −0,078 | 2·10⁻¹⁹ | ✅ | ✅ | bloquea | **bloquea** ✅ |

A n grande cualquier regresión real es significativa; la regla "O" bloquearía por ruido sub-umbral,
la regla "Y" deja pasar −0,03 (correcto) y caza −0,08 (correcto).

**Variante con efecto realmente heterogéneo.** Efecto concentrado en pedidos por debajo de un umbral
hipotético de envío gratis (R$ 150; 22,4 % de los pedidos): lift **+7,05 % en la banda** vs. +1,52 %
fuera; test de interacción `treatment × banda` (log, HC3) **p = 2·10⁻¹⁵**. **El diseño detecta la
heterogeneidad real**, a diferencia del análisis principal (efecto homogéneo → ninguna interacción).

**Todos los pedidos + SE por clúster de cliente.** Con los 97 905 pedidos sin deduplicar y errores
estándar agrupados por cliente: lift **+5,71 %** (vs. +5,67 % deduplicado); el clustering **infla el
SE solo 1,1 %** (el 97 % de los clientes tiene un pedido). Deduplicar fue la opción simple y correcta.

---

## 7. Fase 5 — Evaluación (Evaluation)

> Documento fuente: `docs/05_evaluation.md`. Script: `src/evaluation.py`.

### 7.1 Significancia estadística ≠ relevancia de negocio

| Pregunta | Criterio | Resultado |
|---|---|---|
| ¿Es **estadísticamente** significativo? | p < 0,05 | **Sí** (p ≈ 3·10⁻¹¹) |
| ¿Es **relevante para el negocio**? | IC 95 % del *lift* **enteramente por encima** del MDE (+3 %) | **Sí** — IC [+3,99 %; +7,34 %] (winsor) e [+4,09 %; +8,13 %] (crudo) |

Con n ≈ 47 000 por grupo, un efecto trivial también saldría "significativo". Lo que hace
**accionable** este resultado es que **todo el intervalo de confianza está por encima del umbral de
relevancia de negocio**, no solo el estimador puntual.

### 7.2 Impacto económico estimado

| | Valor |
|---|---|
| Pedidos válidos/año (extrapolación del histórico) | ≈ 58 700 |
| GMV de mercancía anual (base) | ≈ R$ 8,05 M |
| **Uplift de GMV anual** | **+R$ 456 000** · IC 95 % [+R$ 322 000; +R$ 591 000] |
| Uplift de ingreso del marketplace (comisión asumida 15 %) | ≈ +R$ 68 000/año |

Extrapolación lineal del *lift* por pedido al volumen anual; el ingreso real depende del *take rate*.

### 7.3 Estimación ajustada por covariables (ANCOVA)

OLS `AOV_w ~ treatment + n_items + freight + categoría + macro-región + trimestre` (errores HC3):

| | Lift | IC 95 % | SE (R$) |
|---|---:|---:|---:|
| Sin ajuste | +5,67 % | [+3,99 %; +7,34 %] | 1,141 |
| **Con ajuste** | **+5,19 %** | **[+3,71 %; +6,68 %]** | **1,013** |

El ajuste **reduce el error estándar un 11,2 %** (R² del modelo ≈ 0,20) y acerca el estimador al
+5 % verdadero. La reducción de SE es el beneficio robusto; el desplazamiento del punto es en parte
específico de esta muestra y no se vende como propiedad general.

### 7.4 Análisis por segmentos — pre-especificado y con corrección

**Segmentos declarados ANTES de mirar resultados:** `cesta` (1 vs 2+ ítems), `payment_type`,
`macro_region` (5 macrorregiones), `trimestre`, `cat_grupo` (6 categorías top + resto).

> "Nuevos vs. recurrentes" queda **fuera de alcance**, declarado: la dedup a 1 pedido/cliente lo deja
> degenerado (n_recurrentes ≈ 40) y la recompra en Olist es ~3 %.

Test de interacción `treatment × segmento` sobre **log(AOV)**, Wald **HC3** (efecto relativo):

| Segmento | p bruto | p ajustado (BH) | ¿Heterogéneo? |
|---|---:|---:|:--:|
| cesta | 0,92 | 0,92 | ❌ |
| payment_type | 0,38 | 0,92 | ❌ |
| macro_region | 0,68 | 0,92 | ❌ |
| trimestre | 0,79 | 0,92 | ❌ |
| cat_grupo | 0,14 | 0,68 | ❌ |

**Ninguna interacción significativa.** El efecto **relativo** es homogéneo entre segmentos, coherente
con el diseño (los respondedores se sortean al azar). Figura: `f5_01_forest_segmentos.png`.

> **Por qué el test se hace en `log` y no en nivel:** el efecto es multiplicativo, así que el *lift*
> **absoluto** en R$ es mecánicamente mayor en cestas grandes. Un test en nivel detectaría esa
> "heterogeneidad" que no es real — la pregunta de negocio es si el **porcentaje** cambia.

### 7.5 El riesgo de p-hacking — demostrado

Se prueban **38 cortes exploratorios arbitrarios** (estados sueltos, categorías sueltas, cuartiles
de flete, trimestres). Test: interacción `treat × corte`, Wald HC3. Esperados por puro azar a
α = 0,05: **≈ 1,9**.

| Escala del test | Nominales p < 0,05 | Tras BH (FDR) | Tras Bonferroni |
|---|---:|---:|---:|
| **Nivel (R$)** | **5** (3 en cuartiles de flete) | **3** | **2** |
| **Log (efecto relativo, %)** | 2 | **0** | **0** |

**Lecciones:**

1. En **nivel**, varios "segmentos donde el efecto es distinto" **sobreviven incluso a Bonferroni**.
   No son casualidad: son un **artefacto mecánico** del efecto multiplicativo (el *lift* en R$ es
   mayor en cestas grandes), concentrado en los cortes correlacionados con el tamaño (cuartiles de
   flete).
2. En **log** (la magnitud correcta), solo quedan hallazgos nominales de nivel-azar y **ninguno
   sobrevive** a la corrección.
3. → **(a)** testar la magnitud correcta (%, no R$ absolutos); **(b)** pre-especificar los
   segmentos; **(c)** corregir por multiplicidad. **Corregir no basta si el estimando está mal
   planteado.**

### 7.6 Decisión de producto

> # 🟢 LANZAR

| Criterio | ✔ |
|---|---|
| Efecto primario significativo (p ≈ 3·10⁻¹¹) | ✅ |
| IC 95 % del *lift* enteramente por encima del MDE (+3 %) | ✅ [+3,99 %; +7,34 %] |
| Estimación robusta (winsor, log, bootstrap, ANCOVA todas concordantes) | ✅ |
| Ningún guardrail degradado (G1–G4, Benjamini-Hochberg) | ✅ |
| Efecto relativo homogéneo entre segmentos pre-especificados | ✅ |
| Impacto económico material (+R$ 456 k/año GMV) | ✅ |

**Caveats declarados:**

- El efecto es **sintético y conocido**: esta decisión **valida el proceso de decisión**, no
  constituye un hallazgo real sobre Olist.
- Con un ATE inyectado de +2 % o +3 %, la misma regla habría devuelto **ITERAR**; con +0 %,
  **NO LANZAR**. Las tres ramas funcionan.

**Qué vigilar tras un lanzamiento real:** el AOV a 4 semanas frente al +3 % mínimo; la tasa de
devoluciones y reclamaciones (no medibles en Olist); revisar de nuevo a los 90 días para descartar
que el efecto se diluya por novedad.

---

## 8. Fase 6 — Despliegue (Deployment)

> Documento fuente: `docs/06_deployment.md`.

En un proyecto de portfolio el "despliegue" es la **comunicación del resultado** a sus audiencias:

| Entregable | Fichero | Audiencia |
|---|---|---|
| Resumen ejecutivo (1 página) | `docs/resumen_ejecutivo.md` | Stakeholder no técnico |
| Notebook de presentación | `notebooks/ab_test_olist.ipynb` | Revisor técnico / reclutador |
| README del repositorio | `README.md` | Visitante de GitHub |
| Borrador de post de LinkedIn | `docs/linkedin_post.md` | Red profesional |
| Documentación por fase + auditorías | `docs/*.md` | Traza completa del razonamiento |

**Reproducibilidad** (endurecida tras una crítica de revisión): `params.yaml` como única fuente de
verdad; `run_all.py` como único *entrypoint* con informe de reproducibilidad; notebook reducido a
capa de solo lectura (sin ruta de ejecución paralela); suite `pytest` con un test de idempotencia
bit a bit. Detalle en la sección 2.4 y en `docs/06_deployment.md`.

**Ángulo de comunicación elegido:** no "hice un A/B test" (genérico) sino el **hallazgo
metodológico** de que corregir por comparaciones múltiples no protege frente al *p-hacking* si el
*estimando* está mal planteado.

---

## 9. Resultados

> *Redacción tipo TFM: prosa formal, tiempo pasado, con referencia a tablas y figuras. Todos los
> valores proceden de `outputs/tables/*.json`, generados con semilla fija.*

### 9.1 Descripción de la muestra

Tras la preparación de datos (sección 5), la muestra analítica quedó constituida por **94 703
pedidos**, uno por cliente, correspondientes a la ventana temporal 2017-01-01 – 2018-08-31. La
asignación aleatoria produjo **47 280 unidades en el grupo de control y 47 423 en el de
tratamiento** (50,08 %), un reparto compatible con la proporción 50/50 objetivo (χ² = 0,216;
p = 0,642), sin indicio de *Sample Ratio Mismatch*. El equilibrio de covariables entre grupos fue
excelente: las seis covariables consideradas (número de ítems, valor del flete, estado del cliente,
categoría dominante, tipo de pago y mes de compra) presentaron diferencias medias estandarizadas
inferiores a 0,02 en valor absoluto, muy por debajo del umbral convencional de 0,10, y ningún test
ómnibus resultó significativo (p mínimo = 0,32). Sobre la métrica primaria sin perturbar se observó
una diferencia bruta de +1,2 % entre grupos (t de Welch, p = 0,235), atribuible al ruido de
muestreo de la partición.

### 9.2 Validación del diseño experimental

Antes de introducir ningún efecto se realizó una **calibración A/A** consistente en repetir el
contraste sobre 2 000 particiones aleatorias 50/50 de la muestra. La tasa de falsos positivos a
α = 0,05 fue de 4,95 % para el AOV bruto, 5,00 % para el AOV winsorizado y 5,00 % para el AOV en
escala logarítmica, en todos los casos con un intervalo de confianza al 95 % que contiene el valor
nominal de 0,05. La distribución de los p-valores resultó indistinguible de una uniforme (test de
Kolmogórov–Smirnov, p ≥ 0,53 en las tres métricas; Figura `f4_02_aa_pvalores.png`). Se concluye que
el procedimiento de análisis **no genera falsos positivos** y que sus p-valores están correctamente
calibrados.

El **análisis de potencia a priori** determinó que, con el tamaño muestral disponible (n ≈ 47 000
por grupo), el efecto relativo mínimo detectable al 80 % de potencia y α = 0,05 bilateral es de
+2,79 % sobre el AOV bruto y de +2,34 % sobre el AOV winsorizado, ambos por debajo del umbral de
relevancia de negocio (+3 %). La potencia para detectar el efecto declarado (+5 %) fue
prácticamente del 100 %. Mediante simulación (1 000 réplicas) se comprobó que la **heterogeneidad
del efecto**, esperada como fuente de pérdida de potencia, tiene un impacto despreciable en este
contexto: la penalización de potencia por el efecto diluido frente a un efecto uniforme del mismo
tamaño medio fue inferior a 0,2 puntos porcentuales al tamaño del experimento e inferior a 1 punto
porcentual en todo el rango de tamaños muestrales examinado (Figura `f4_04_power_vs_n.png`). El
estimador del efecto resultó insesgado en la simulación (media de 1 000 réplicas: 4,999 % en la
métrica bruta y 5,006 % en la winsorizada).

Adicionalmente, se repitió el experimento A/B completo —incluyendo la re-partición aleatoria y la
re-inyección del efecto— sobre 500 semillas. En la métrica bruta el estimador fue insesgado (sesgo
medio de −0,03 puntos porcentuales) y el intervalo de confianza al 95 % cubrió el efecto verdadero
en el 94 % de las réplicas, coherente con su cobertura nominal. En la métrica winsorizada se
detectó un **sesgo negativo de −0,36 puntos porcentuales** y una cobertura reducida al 92 %, debido
a que la winsorización recorta con mayor probabilidad los valores elevados del grupo de tratamiento,
inflados por el efecto multiplicativo. Este sesgo es el precio de la reducción de varianza que
aporta la winsorización, y no altera la decisión, dado que ambos intervalos de confianza superan el
umbral de relevancia. El resultado puntual obtenido con la semilla del análisis principal (+5,7 %)
se sitúa dentro del rango intercuartílico ampliado [p2,5; p97,5] = [+2,9 %; +7,1 %] de la
distribución de réplicas.

### 9.3 Verificación de supuestos del test

El AOV presenta una distribución fuertemente asimétrica (coeficiente de asimetría = 9,77) y
leptocúrtica (curtosis en exceso = 271,4), por lo que el supuesto de normalidad de las
observaciones se rechaza de forma contundente (test de D'Agostino, p ≈ 0). Sin embargo, la
**distribución muestral de la media** es compatible con la normalidad (test de D'Agostino sobre
5 000 medias bootstrap de tamaño n ≈ 47 000: K² = 0,38; p = 0,826), consecuencia del Teorema
Central del Límite a este tamaño muestral. El test de Levene sobre la homogeneidad de varianzas
entre grupos no fue significativo en ausencia de efecto (p = 0,205) pero **sí lo fue tras la
inyección del efecto diluido** (p = 1,6·10⁻⁶), reflejando que un efecto multiplicativo aplicado a
una fracción de los pedidos incrementa la varianza del grupo de tratamiento. En consecuencia, se
adoptó la **t de Welch** como contraste primario, en lugar de la t de Student, por su robustez
frente a la heterocedasticidad. La independencia de las observaciones queda garantizada por diseño
(asignación aleatoria y deduplicación a un pedido por cliente), asumiéndose ausencia de
interferencia entre clientes (SUTVA).

### 9.4 Resultado principal

El contraste primario —t de Welch sobre el AOV winsorizado al percentil 99,5— arrojó un incremento
del valor medio del pedido en el grupo de tratamiento de **+5,67 %** (diferencia absoluta de
R$ 7,58 por pedido), con un intervalo de confianza al 95 % de **[+3,99 %; +7,34 %]** y un p-valor de
**3,1·10⁻¹¹** (t = 6,64; grados de libertad de Welch ≈ 94 405; n_control = 47 280,
n_tratamiento = 47 423). Sobre la métrica sin winsorizar el incremento estimado fue de **+6,11 %**
(IC 95 % [+4,09 %; +8,13 %]; p = 3,1·10⁻⁹). El efecto verdadero inyectado (+5,0 %) queda **contenido
en ambos intervalos de confianza**. El estimador puntual supera el valor inyectado como
consecuencia del desbalance basal de la partición descrito en 9.1 (+1,2 %, no significativo); el
análisis multi-semilla (9.2) confirma que el estimador es insesgado en repetición.

Los análisis de robustez fueron concordantes: el intervalo de confianza bootstrap (10 000 réplicas,
sin supuesto distribucional) fue [+4,05 %; +8,19 %]; el contraste sobre el cociente de medias
geométricas (escala logarítmica) estimó un +4,79 % (p = 1,4·10⁻¹⁴); y el test de Mann–Whitney para
dominancia estocástica resultó igualmente significativo (p = 1,8·10⁻¹⁵). El **ajuste por
covariables** mediante ANCOVA (regresión con errores robustos HC3, R² ≈ 0,20) redujo el error
estándar del estimador en un 11,2 % y situó la estimación en **+5,19 %** (IC 95 % [+3,71 %;
+6,68 %]), más próxima al valor verdadero. La Figura `f4_03_ab_efecto.png` resume las estimaciones
puntuales e intervalares.

### 9.5 Métricas guardrail

Ninguna de las cuatro métricas de control mostró degradación. Tras la corrección de
Benjamini–Hochberg, la puntuación media de reseña (4,114 en control frente a 4,116 en tratamiento;
p ajustado = 0,80), la tasa de cancelación (0,541 % frente a 0,570 %; p ajustado = 0,77), el valor
medio del flete (R$ 22,74 frente a R$ 22,89; p ajustado = 0,77) y el número medio de ítems por
pedido (1,140 frente a 1,138; p ajustado = 0,77) resultaron estadísticamente indistinguibles entre
grupos. Este resultado es el esperado, dado que el diseño inyecta el efecto exclusivamente sobre la
métrica primaria. La capacidad de los contrastes de guardrail para detectar una regresión real se
verificó de forma independiente: la inyección de una caída de −0,08 puntos en la puntuación de
reseña fue correctamente identificada como degradación bajo la regla de dos puertas (p = 2·10⁻¹⁹;
magnitud ≥ 0,05), mientras que una caída sub-umbral de −0,03 puntos —estadísticamente significativa
a este tamaño muestral (p = 0,001) pero por debajo del umbral de relevancia— no activó la alarma,
comportamiento deseado.

### 9.6 Análisis por segmentos

El análisis de heterogeneidad del efecto se realizó sobre cinco segmentos pre-especificados
(tamaño de cesta, tipo de pago, macrorregión, trimestre y grupo de categoría), mediante contrastes
de interacción `tratamiento × segmento` en escala logarítmica con errores robustos HC3 y corrección
de Benjamini–Hochberg. **Ningún contraste resultó significativo** (p bruto mínimo = 0,14; todos los
p ajustados ≥ 0,68), indicando que el efecto relativo es homogéneo entre segmentos, en coherencia
con el diseño de la simulación. La Figura `f5_01_forest_segmentos.png` muestra las estimaciones por
nivel, todas compatibles con el efecto global.

Como demostración del riesgo de *p-hacking*, se realizó a continuación un barrido exploratorio de
38 cortes arbitrarios de la muestra. En escala de nivel (R$), cinco cortes presentaron interacción
nominalmente significativa —frente a los ≈ 1,9 esperados por azar— y tres de ellos sobrevivieron a
la corrección de Benjamini–Hochberg, dos incluso a la de Bonferroni; los cortes afectados se
concentraron en los cuartiles de valor de flete, variable correlacionada con el tamaño del pedido.
Estos hallazgos **no son fruto del azar sino un artefacto del efecto multiplicativo**, que produce
un incremento absoluto mayor en los pedidos de mayor valor. Al repetir el análisis en escala
logarítmica —la magnitud pertinente para la pregunta de negocio— solo se observaron dos hallazgos
nominales, ninguno de los cuales sobrevivió a la corrección por multiplicidad.

### 9.7 Traducción a decisión de producto

El efecto primario es **estadísticamente significativo** (p ≈ 3·10⁻¹¹) y, sobre todo,
**materialmente relevante**: el intervalo de confianza al 95 % del incremento del AOV se sitúa
enteramente por encima del umbral de relevancia de negocio (+3 %), derivado del modelo de
*break-even*. La estimación es robusta a la especificación (winsorización, escala logarítmica,
bootstrap y ajuste por covariables producen conclusiones concordantes), ninguna métrica de control
se degrada y el efecto es homogéneo entre los segmentos pre-especificados. El impacto económico
estimado, bajo extrapolación lineal al volumen anual histórico, asciende a **+R$ 456 000 anuales de
valor de mercancía** (IC 95 % [+R$ 322 000; +R$ 591 000]). En consecuencia, la regla de decisión
devuelve **LANZAR**. Un barrido de la regla sobre distintos tamaños de efecto confirma que las tres
decisiones posibles (NO LANZAR, ITERAR, LANZAR) son alcanzables, y que un efecto de +2 % o +3 %
habría conducido a "ITERAR".

---

## 10. Limitaciones

Síntesis consolidada de las tres auditorías del proyecto (`docs/auditoria_fase1_fase2.md`,
`docs/auditoria_fase5.md`, `docs/auditoria_global.md`).

| # | Limitación | Severidad | ¿Intrínseca al dataset? | Estado |
|---|---|---|---|---|
| 1 | **El experimento es simulado** → validez externa nula. El proyecto no describe nada real sobre Olist. | Alta (es el planteamiento) | **Sí** | Declarada en todos los entregables; el proyecto valida el *proceso*. |
| 2 | **El modelo del efecto condiciona resultados.** Dos elecciones importan: (a) los respondedores se sortean al azar → la homogeneidad entre segmentos está en parte "horneada" en el diseño; (b) el efecto es multiplicativo → genera el artefacto que explota la demo de p-hacking. Un modelo de la barra de envío gratis concentraría el efecto por debajo de un umbral (efecto heterogéneo real). | Media | Parcial | Consecuencias analizadas explícitamente; §6.8 añade una variante heterogénea y muestra que el diseño la detecta. |
| 3 | **MDE de relevancia = +3 %.** | Media | No | **Resuelta**: `src/mde_cost_model.py` lo deriva de un *break-even*; válido para volumen ≥ ~415 000 pedidos/año. |
| 4 | **Un solo *split* de análisis** (SEED 42), con +1,2 % de desbalance basal que infla el estimador puntual. | Baja-Media | No | **Resuelta**: §6.8 A/B multi-semilla (500) → crudo insesgado, cobertura del IC 0,94. |
| 5 | **Guardrails sin efecto inyectado** → "no degradación" trivialmente cierta; no demostraría por sí sola que los tests cazarían una regresión. | Media | No | **Resuelta**: §6.8 inyecta regresiones en G1 y verifica la regla de dos puertas. |
| 6 | **Sin métrica de retención / LTV.** La recompra en Olist (~3 %) y la ventana lo impiden. | Baja | **Sí** | Declarada; queda fuera del alcance. |

**Limitaciones adicionales:**

- **Extrapolación económica lineal.** El *uplift* de GMV asume que el *lift* por pedido se mantiene
  al escalar a todo el volumen y en el tiempo; ignora novedad, saturación y estacionalidad. La
  comisión del 15 % es una asunción ilustrativa (Olist no publica su *take rate*).
- **Sesgo de la winsorización.** La winsorización, elegida para reducir varianza, introduce un
  sesgo puntual de −0,36 pp en el estimador del *lift* y una infra-cobertura del IC (0,92 frente a
  0,95). Se mitiga reportando también la métrica cruda (insesgada, cobertura nominal).
- **Ventana temporal de 2 años**, no un experimento de 2–4 semanas: el "tiempo en experimento" no
  es realista, aunque la estacionalidad queda balanceada por la aleatorización.
- **Segmentos observacionales.** El análisis por segmentos usa covariables de pre-tratamiento; no
  se explora *new vs returning* por la degeneración descrita en 7.4.

**Ninguna limitación invalida el trabajo.** Las nº 1 y 6 son consecuencia inevitable de elegir un
dataset público de e-commerce sin experimento; las nº 3, 4 y 5 se abordaron en una segunda pasada;
persiste un residuo de la nº 2 (la forma funcional del efecto es una elección declarada).

### 10.1 ¿Son solucionables estas limitaciones?

De las ocho limitaciones, **dos son estructurales** (no eliminables con este dataset y este
escenario) y **seis son solucionables o ya están resueltas**.

| # | Limitación | ¿Solucionable? | Cómo / por qué no |
|---|---|:--:|---|
| 1 | Experimento simulado → validez externa nula | ❌ **No**, sin cambiar la premisa | La única forma de arreglarlo es un dataset con **aleatorización real** (Criteo Uplift, Hillstrom, X5 RetailHero). Pero entonces la palanca deja de ser un cambio *on-site* en el checkout y pasa a ser un envío de marketing (email/SMS) → se cambia una limitación por otra. Los experimentos de producto reales **son propietarios y no se publican**. Mitigación posible: correr el mismo pipeline sobre Hillstrom como anexo → valida la maquinaria con datos reales, sin hacer real el análisis de Olist. |
| 6 | Sin métrica de retención / LTV | ❌ **No**, con Olist | La recompra en Olist es ~3 % y la ventana es corta. Necesitaría un dominio con recompra natural (suscripción, telco) o un dataset como *DunnHumby — The Complete Journey* (2 años, hogares) — pero ese tiene campañas *targeted*, no aleatorizadas. Es una decisión de alcance, declarada. |
| 3 | MDE de relevancia = +3 % | ✅ **Ya resuelta** | Pasó de asertado a **derivado** de un modelo de *break-even* (`src/mde_cost_model.py`). Mejorable solo con datos de coste reales, que no existen públicamente. |
| 4 | Un solo *split* (SEED 42) | ✅ **Ya resuelta** | El A/B multi-semilla (500 réplicas) demuestra que el estimador es insesgado y el IC tiene cobertura 0,94. Se podría poner la media de las 500 como titular en vez del *split* 42. |
| 5 | Guardrails sin efecto inyectado | ✅ **Ya resuelta (para G1)** | §6.8 inyecta regresiones en `review_score` y verifica que la regla de dos puertas caza −0,08 y deja pasar −0,03. Extensible a G2/G3/G4 en ~1 h. |
| 2 | El modelo del efecto condiciona resultados (homogeneidad, artefacto de p-hacking) | 🟡 **Sí, con trabajo** | Promover la variante heterogénea de §6.8 a escenario principal; correr el análisis bajo 2–3 modelos de efecto (multiplicativo / aditivo / diluido) y mostrar qué conclusiones son sensibles al modelo. Lo convierte en un **análisis de sensibilidad transparente** en vez de una elección oculta. Residuo: cualquier efecto sintético sigue siendo una elección. |
| — | Extrapolación económica lineal · comisión 15 % inventada | 🟡 **Mejorable** | Usar rangos de *take rate* publicados (Olist ~10–20 %) y una tabla de sensibilidad en vez de un punto. No hay cifras reales de Olist. |
| — | Sesgo de winsorización −0,36 pp | ✅ **Solucionable** | Usar un estimador robusto insesgado (media truncada + IC bootstrap-BCa, o Hodges–Lehmann) en vez de winsorizar; o poner la métrica cruda como titular (ya insesgada). |
| — | Ventana de 2 años ≠ experimento de 2–4 semanas | 🟡 **Solucionable con coste** | Restringir a un tramo de 3 semanas y re-ejecutar → n baja de 94 k a ~5 k, el MDE detectable sube a ~10 %. Muestra el escenario de duración realista pero se pierde potencia. |

**Lectura para un portfolio.** El estado actual es bueno: un revisor valora más «conoce sus
limitaciones y las dice» que «las esconde». Las mejoras pendientes son de rendimiento decreciente, y
hacer desaparecer la limitación nº 1 requeriría datos propietarios (no disponibles) o un escenario
más débil.

---

## 11. Discusión y conclusiones

### 11.1 Qué demuestra el proyecto

El proyecto ejecuta el ciclo completo de un análisis de experimentación de producto con criterio de
nivel *senior*:

1. **Disciplina de pre-especificación.** Hipótesis, métrica primaria única, guardrails, MDE y regla
   de decisión se escriben **antes** de mirar los datos, y el orden se mantiene en toda la
   documentación.
2. **Separación de significancia y relevancia** con una regla operativa (IC frente a MDE), no un
   discurso.
3. **Verificación de supuestos que cambia la decisión** (Welch en lugar de Student por
   heterocedasticidad bajo H1): no es una comprobación decorativa.
4. **Calibración A/A** sobre 2 000 particiones — la forma correcta de certificar un pipeline de
   experimentación nuevo — y **A/B multi-semilla** para la cobertura del intervalo de confianza.
5. **Cuantificación de una predicción propia y su refutación** (la penalización por dilución
   resultó despreciable), y reporte honesto del sesgo introducido por la winsorización.
6. **Control de p-hacking**: pre-especificación, corrección por multiplicidad y una demostración de
   que la escala equivocada del estimando fabrica hallazgos que ni Bonferroni elimina.
7. **Trazabilidad y reproducibilidad**: parámetros en un único fichero, un único *entrypoint* con
   informe de reproducibilidad, notebook de solo lectura, y suite de tests con comprobación de
   idempotencia.
8. **Autocrítica documentada**: tres auditorías que encontraron y corrigieron problemas reales
   (F-test → Wald HC3; "casi normal" → matizado; parámetro duplicado → `config.py`).

### 11.2 Hallazgos metodológicos

- La **heterogeneidad del efecto no penaliza la potencia de forma apreciable** cuando la varianza
  natural de la métrica es alta (CV ≈ 1,5). La intuición contraria es correcta en dirección pero no
  en magnitud, y solo se descubre cuantificándola.
- **A tamaños muestrales grandes, cualquier regresión real de un guardrail es significativa.** La
  regla de guardrail debe combinar **significancia y magnitud** (dos puertas); una regla basada
  solo en significancia bloquea lanzamientos por ruido irrelevante.
- **La winsorización no es gratuita.** Aplicada a una métrica sobre la que actúa un efecto
  multiplicativo, introduce un sesgo negativo en el estimador del *lift*. Reduce el error cuadrático
  medio (menor varianza compensa el sesgo) pero degrada la cobertura del intervalo de confianza. La
  recomendación práctica es reportar ambas versiones.
- **Corregir por comparaciones múltiples no salva un estimando mal planteado.** Testar el efecto en
  valor absoluto (R$) en lugar de en porcentaje, sobre cortes correlacionados con el tamaño de
  cesta, produce "segmentos ganadores" que sobreviven incluso a Bonferroni. La defensa correcta es
  triple: magnitud correcta, pre-especificación y corrección.

### 11.3 Conclusión

Para el objetivo planteado —un proyecto de portfolio que demuestre competencia en diseño y análisis
de experimentos de producto en un dominio de marketplace— el trabajo cumple con creces. Las
decisiones están justificadas, las alternativas consideradas y, sobre todo, **las limitaciones están
declaradas en lugar de escondidas**. La limitación de fondo (el experimento es simulado) es
inevitable con un dataset público de e-commerce y se gestiona con transparencia: el proyecto no
pretende haber descubierto nada sobre Olist, sino demostrar que sabe **diseñar, ejecutar, auditar y
decidir** un experimento.

---

## 12. Trabajo futuro

1. **Guardrail con regresión sub-umbral graduada:** ampliar §6.8 con un barrido de magnitudes de
   regresión en varios guardrails y curvas de potencia de detección.
2. **Efecto heterogéneo realista como escenario principal:** convertir la variante de §6.8 (efecto
   concentrado bajo el umbral de envío gratis) en un análisis completo, con potencia para detectar
   la heterogeneidad y estimación del efecto por banda.
3. **Diseño con periodo pre-tratamiento sintético** para aplicar CUPED y comparar la reducción de
   varianza frente a la ANCOVA.
4. **Modelo de costes calibrado** con datos de un marketplace real (o rangos publicados) para fijar
   el MDE de relevancia sin asunciones ilustrativas.
5. **Análisis secuencial / *always-valid* p-values** para simular la práctica real de mirar
   resultados antes de tiempo.
6. **Réplica sobre un dataset con aleatorización real** (Hillstrom, Criteo Uplift) como validación
   externa del pipeline, aceptando que la palanca sería un envío de marketing.

---

## 13. Anexos

### Anexo A — Parámetros del experimento (`params.yaml`)

| Parámetro | Valor | Significado |
|---|---|---|
| `seed` | 42 | semilla global |
| `alpha` | 0,05 | nivel de significación (bilateral) |
| `effect.p_resp` | 0,20 | fracción de tratados que responde |
| `effect.delta_resp` | 0,25 | efecto multiplicativo entre respondedores |
| `effect.eps_sd` | 0,05 | ruido gaussiano sobre el efecto |
| *ATE* (derivado) | 0,05 | efecto medio = `p_resp · delta_resp` |
| `mde_relevancia_pct` | 3,0 | *lift* mínimo relevante (derivado del *break-even*) |
| `target_power` | 0,80 | potencia objetivo |
| `window_start` / `window_end` | 2017-01-01 / 2018-09-01 (excl.) | ventana temporal |
| `winsor_q` | 0,995 | percentil de winsorización (solo contraste) |
| `n_sim_aa` | 2 000 | particiones para la calibración A/A |
| `n_sim_power` | 1 000 | réplicas del *power analysis* simulado |
| `n_sim_multiseed` | 500 | réplicas del A/B completo |
| `n_bootstrap` | 10 000 | remuestreos del IC bootstrap |
| `cost_model.*` | ver `params.yaml` | asunciones del modelo de *break-even* del MDE |

### Anexo B — Glosario

| Término | Definición |
|---|---|
| **AOV** | *Average Order Value*, valor medio del pedido. Aquí, valor de mercancía (Σ `price`), excluido el flete. |
| **ATE** | *Average Treatment Effect*, efecto medio del tratamiento. Aquí, +5 % por construcción. |
| **MDE** | *Minimum Detectable Effect*. Se usa en dos sentidos: (a) el efecto mínimo que el diseño detecta al 80 % de potencia; (b) el *MDE de relevancia*, el efecto mínimo que justifica el coste del cambio. |
| **Guardrail** | Métrica de control que no debe degradarse aunque la primaria mejore. |
| **SMD** | *Standardized Mean Difference*, diferencia de medias estandarizada. Criterio de balance: \|SMD\| < 0,10. |
| **SRM** | *Sample Ratio Mismatch*, desviación del reparto de unidades respecto al ratio objetivo (aquí 50/50). |
| **Test A/A** | Experimento sin efecto: control contra control. Sirve para verificar que el pipeline no genera falsos positivos. |
| **Efecto diluido** | Modelo en el que solo una fracción de los tratados responde. |
| **Winsorización** | Recorte de los valores extremos de una variable a un percentil dado. |
| **t de Welch** | Variante de la t de Student que no asume varianzas iguales entre grupos. |
| **Benjamini–Hochberg (BH)** | Procedimiento que controla la tasa de falsos descubrimientos (FDR) en contrastes múltiples. |
| **Bonferroni** | Corrección más estricta: controla la probabilidad de *algún* falso positivo (FWER). |
| **ANCOVA** | Análisis de covarianza: regresión del *outcome* sobre el tratamiento más covariables predictoras, para reducir varianza. |
| **HC3** | Estimador de errores estándar robusto a heterocedasticidad. |
| **CLT / TCL** | Teorema Central del Límite: la media muestral tiende a normal aunque los datos no lo sean. |
| **SUTVA** | *Stable Unit Treatment Value Assumption*: sin interferencia entre unidades. |
| **CUPED** | *Controlled-experiment Using Pre-Experiment Data*: técnica de reducción de varianza con datos previos. |

### Anexo C — Cómo reproducir

```bash
pip install -r requirements.txt

# datos (no versionados por la licencia CC BY-NC-SA 4.0)
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip

python run_all.py        # ~2 min · 6 fases + informe de reproducibilidad (falla con código !=0 si algo no cuadra)
pytest                   # tests rápidos
pytest -m slow           # + idempotencia bit a bit

jupyter notebook notebooks/ab_test_olist.ipynb   # capa de presentación (solo lee outputs/)
```

### Anexo D — Índice de figuras

| Figura | Fase | Contenido |
|---|---|---|
| `f2_01_volumen_mensual.png` | 2 | Volumen mensual de pedidos; ventana estable |
| `f2_02_distribucion_aov.png` | 2 | Distribución del AOV: bruto (skew 9,8) vs. log (casi normal) |
| `f2_03_guardrails.png` | 2 | `review_score` y pedidos por cliente |
| `f3_01_balance.png` | 3 | *Love-plot* del balance de covariables |
| `f4_01_tcl_normalidad.png` | 4 | Datos no normales; media normal (TCL) |
| `f4_02_aa_pvalores.png` | 4 | A/A: histograma plano de p-valores |
| `f4_03_ab_efecto.png` | 4 | Efecto del A/B con IC 95 % (varios métodos) |
| `f4_04_power_vs_n.png` | 4 | Potencia vs. n: efecto uniforme vs. diluido |
| `f5_01_forest_segmentos.png` | 5 | *Forest plot* del efecto por segmento |
| `f_mde_breakeven.png` | 4 | MDE de relevancia derivado de costes |

### Anexo E — Historial de decisiones auditadas

| ID | Decisión | Sección | Resultado de la auditoría |
|---|---|---|---|
| D1 | Métrica primaria = AOV | 3.3 | Correcta; alternativa honesta era esta o cambiar de dataset |
| D2 | Aleatorizar por cliente; dedup a 1 pedido/cliente | 3.4 | Correcta y verificada (impacto −0,35 %) |
| D3 | Test bilateral, α = 0,05 | 3.5 | Correcta y conservadora |
| D4 | Guardrails + regla de dos puertas + BH | 3.6 | Regla corregida de "O" a "Y" tras la auditoría |
| D5 | MDE de relevancia = +3 % | 3.7 | Pasó de asertado a **derivado** de un modelo de costes |
| D6 | Regla LANZAR/ITERAR/NO LANZAR | 3.8 | Excelente; las tres ramas verificadas |
| D7 | Simulación A/A + A/B diluido | 3.9 | Bien documentada; forma funcional del efecto sigue siendo una elección declarada |
| D8 | Ventana temporal 2017-01/2018-08 | 4.2 | Cosmética, no correctiva; bien no sobrevendida |
| D9 | Winsorización p99,5 solo para el contraste | 5.4 | Bien gestionada; se descubre que introduce −0,36 pp de sesgo → se reportan ambas |
| — | Tests de interacción: F homocedástico → Wald HC3 | 7.4–7.5 | Corregido tras la auditoría de la Fase 5; refuerza la demo de p-hacking |

---

*Documento generado como parte del proyecto. Para la versión ejecutable y todos los datos
intermedios, ver el repositorio.*
