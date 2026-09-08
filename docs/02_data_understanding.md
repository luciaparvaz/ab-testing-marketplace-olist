# Fase 2 — Comprensión de los datos (Data Understanding)

> CRISP-DM · Fase 2 de 6
> Script reproducible: `src/profiling_fase2.py` → `outputs/tables/fase2_resumen.json`
> Figuras: `outputs/figures/f2_01…03.png`

---

## 2.1 Procedencia, licencia y estructura

| | |
|---|---|
| **Fuente** | Brazilian E-Commerce Public Dataset by Olist — Kaggle (`olistbr/brazilian-ecommerce`) |
| **Publicador** | Olist Store (marketplace brasileño) |
| **Licencia** | **CC BY-NC-SA 4.0** — verificada en la descarga vía Kaggle CLI (`License(s): CC-BY-NC-SA-4.0`). Uso no comercial, atribución y *share-alike*. Compatible con el uso de portfolio; los CSV crudos **no se versionan** en el repo. |
| **Descarga** | `kaggle datasets download -d olistbr/brazilian-ecommerce` (42,6 MB comprimido) |
| **Formato** | 9 CSV relacionales, unidos por claves (`order_id`, `customer_id`, `product_id`, `seller_id`) |

### Tablas y volúmenes

| Tabla | Filas | Columnas | Uso en el experimento |
|---|---:|---:|---|
| `olist_orders_dataset` | 99.441 | 8 | espina dorsal: 1 fila/pedido, estado, timestamps |
| `olist_order_items_dataset` | 112.650 | 7 | **métrica primaria**: `price`, `freight_value` por ítem |
| `olist_order_payments_dataset` | 103.886 | 5 | robustez de importe (`payment_value`), método de pago |
| `olist_order_reviews_dataset` | 99.224 | 7 | **guardrail G1**: `review_score` |
| `olist_customers_dataset` | 99.441 | 5 | **unidad de aleatorización**: `customer_unique_id`, `customer_state` |
| `olist_products_dataset` | 32.951 | 9 | segmentación por categoría |
| `olist_sellers_dataset` | 3.095 | 4 | contexto marketplace |
| `olist_geolocation_dataset` | ~1 M | 5 | no se usa (ruido, no aporta a la pregunta) |
| `product_category_name_translation` | 71 | 2 | traducción de categorías PT→EN |

---

## 2.2 Período y ventana de análisis

- **Rango bruto:** 2016-09-04 a 2018-10-17.
- **Realidad del dataset:** 2016-09/10 son testimoniales (4 + 324 pedidos), 2016-11 está **vacío**, y 2018-09/10 tienen 16 + 4 pedidos (corte de exportación). El grueso está entre **2017-01 y 2018-08**.
- **Decisión (confirmada):** restringir a la **ventana estable 2017-01 → 2018-08** para (i) eliminar el arranque ralo y la cola incompleta y (ii) que el volumen y la duración se asemejen a los de un experimento real. Impacto en n: se pierde <1 % de los pedidos válidos y el AOV medio cambia de R$ 137,42 a R$ 137,37 (auditoría §B6) → es un ajuste **por realismo, no una corrección de sesgo**.
- Como la asignación será **aleatoria por cliente**, *treatment* y *control* cubrirán el mismo rango de fechas → **la estacionalidad queda balanceada por diseño** (ver `f2_01_volumen_mensual.png`).

---

## 2.3 Métrica primaria: perfilado del AOV

`merch_value` = Σ `price` de los ítems por `order_id` (excluye flete). Pedidos válidos = estado en
{delivered, shipped, invoiced, approved, processing} y con al menos un ítem → **n = 98.199 pedidos /
94.983 clientes únicos**.

| Estadístico | `merch_value` (primaria) | `merch + freight` | `log(merch_value)` |
|---|---:|---:|---:|
| n | 98.199 | 98.199 | 98.199 |
| media | **R$ 137,42** | R$ 160,24 | 4,443 |
| mediana | R$ 86,90 | R$ 105,28 | 4,465 |
| desv. típica | R$ 209,31 | R$ 219,11 | 0,932 |
| **CV (σ/μ)** | **1,523** | 1,367 | 0,210 |
| p95 / p99 | R$ 400 / R$ 995 | R$ 449 / R$ 1.055 | 5,99 / 6,90 |
| máx | R$ 13.440 | R$ 13.664 | 9,51 |
| **skew** | **9,77** | 9,26 | **0,24** |
| curtosis (exceso) | 271,4 | 244,1 | 0,33 |

**Lecturas clave (condicionan la Fase 4):**

1. **El AOV bruto es extremadamente asimétrico y leptocúrtico** (skew ≈ 9,8; cola hasta R$ 13.440
   frente a mediana R$ 87). Ver `f2_02_distribucion_aov.png`.
2. **La transformación log lleva la asimetría y la curtosis a un rango robusto** (skew 9,8 → 0,24;
   curtosis 271 → 0,33). Formalmente **sigue sin ser normal** (D'Agostino K² p ≈ 8·10⁻²⁴ a n = 5.000
   — auditoría §B1), pero eso es irrelevante: con n grande la media es normal por el TCL. **El
   t-test sobre `log(AOV)` NO es el primario**: contrasta el **cociente de medias geométricas**
   (≈ mediana), que es otra pregunta de negocio, no una versión "con más potencia" del AOV
   (auditoría §B2). Entra como **robustez**.
3. Con **n ≈ 47–48 k por grupo** (tras dedup a 1 pedido/cliente y ventana temporal), el Teorema
   Central del Límite hace que la **distribución muestral de la media sea normal pese al skew**, por
   lo que la **t de Welch sobre el valor bruto es el test primario** (el negocio quiere la media,
   porque revenue = media × volumen). Se confirma empíricamente con el A/A de la Fase 4.
4. Los **outliers de cola** (máx R$ 13.440) inflan la varianza. **Decisión (auditoría §B4):**
   winsorización **p99,5 solo para el contraste** (recorta 0,50 % de obs, baja el CV 1,52 → 1,28);
   el **AOV base descriptivo se reporta SIN winsorizar** (R$ 137,42), porque winsorizar desplaza la
   media un −2,4 %. Se reporta el test **con y sin** winsorización.

### Preview de potencia (preliminar — no es la validación)

Con `TTestIndPower` (aprox. normal), n ≈ 49 k/grupo, α = 0,05 bilateral, potencia 0,80:

| Escenario | CV | Lift relativo detectable |
|---|---:|---:|
| AOV crudo | 1,523 | **+2,72 %** |
| AOV winsorizado p99,5 | 1,278 | **+2,28 %** |

→ Ambos por debajo del **MDE de relevancia de +3 %**, pero con **margen estrecho**. Esta cifra es
una **cota superior en el peor caso** y **no** es la base de la conclusión de "muestra potente": la
validación real es la **potencia empírica al efecto diluido inyectado** (§1.7b), medida por
simulación repetida en la Fase 4. Con efecto **diluido** la potencia real será **menor** que la
nominal — resultado esperado del proyecto, no un fallo.

---

## 2.4 Métricas guardrail: perfilado

| Guardrail | Valor base | Notas |
|---|---|---|
| **G1 — `review_score`** | media **4,12** / 5 · σ 1,32 · cobertura **99,3 %** | Distribución en U-invertida sesgada: 58 % son 5★, 11 % son 1★ (`f2_03_guardrails.png`). No normal → Mann–Whitney o test de proporción "≥ 4" como complemento del t-test. |
| **G2 — tasa de cancelación** | **0,63 %** global (625 / 99.441) | Evento raro → test de proporciones (z) o Fisher; baja potencia, se reportará con IC amplio. |
| **G3 — `freight_value`** | media **R$ 22,82** / pedido · CV 0,95 | Vigilar que un alza de AOV no venga acompañada de mayor flete asumido. |
| **G4 — pedidos por cliente** | ver §2.5 | Que el AOV no suba a costa de menor frecuencia. |

---

## 2.5 Unidad de aleatorización: pedidos por cliente

| | |
|---|---:|
| Clientes únicos (válidos) | 94.983 |
| Con exactamente 1 pedido | 92.096 (**96,96 %**) |
| Con 2 o más pedidos | 2.887 (3,04 %) |
| % de pedidos que provienen de clientes recurrentes | **6,21 %** |
| Máx. pedidos de un cliente | 16 |

→ Randomizar por `customer_unique_id` es **casi equivalente** a randomizar por pedido (evita
contaminación). **Decisión (auditoría §B3):** deduplicar a **1 pedido por cliente** (el primero de
la ventana). Verificado: mueve el AOV medio solo **−0,35 %** (R$ 137,42 → 137,90), y a cambio
**unidad de aleatorización = unidad de análisis** (sin necesidad de SE por clúster). n de análisis
resultante ≈ 94 k clientes (antes de aplicar la ventana temporal). Robustez: análisis con todos los
pedidos + SE por clúster de cliente.

---

## 2.6 Calidad de los datos (hallazgos que la Fase 3 debe tratar)

| Hallazgo | Magnitud | Tratamiento previsto (Fase 3) |
|---|---|---|
| Pedidos sin ítems | 775 (mayoría `unavailable` / `canceled`) | Excluir de la métrica primaria; contar en G2. |
| `review_id` duplicados | 814 | Deduplicar. |
| `order_id` con >1 review | 551 | Quedarse con la review de **`review_answer_timestamp` más reciente** (no por orden de fila — afecta a 100 pedidos, auditoría §B5). |
| `order_approved_at` nulo | 160 | No afecta a la métrica primaria; documentar. |
| `order_delivered_customer_date` nulo | 2.965 | Solo afecta a métricas de entrega (no guardrail principal). |
| `payment_value` ausente en pedido válido | 1 | Documentar; la métrica primaria sale de `order_items`, no de pagos (auditoría §B7). |
| Estados no finales (`shipped`, `invoiced`, `processing`, `approved`) | ~1.700 | Incluidos como "compra realizada"; análisis de sensibilidad restringiendo a `delivered`. |
| Outliers de AOV (cola pesada) | p99 = R$ 995; máx R$ 13.440 | Winsorización declarada **p99,5** solo para el contraste; AOV base descriptivo sin winsorizar; reportar con y sin. |
| `payment_type = not_defined` | 3 | Descartar. |

---

## 2.7 Limitaciones que afectan a la validez del experimento

1. **No hay aleatorización real ni capa de tráfico.** El dataset arranca en el pedido: no hay
   sesiones, visitas ni carritos → **no se puede medir conversión**. La métrica primaria es el AOV
   (§1.2). La asignación control/tratamiento se **simula** (§1.7); el efecto del A/B se **inyecta de
   forma declarada** con un modelo **diluido** (20 % de tratados responden con +25 %; ATE = +5 %).
   En consecuencia, el proyecto demuestra **rigor de diseño y de análisis**, no un hallazgo de
   negocio genuino.
2. **Efecto de tratamiento no observado en covariables.** Al simular, el rediseño solo puede actuar
   sobre la métrica que nosotros perturbamos; en la realidad afectaría también al mix de categorías,
   la tasa de devolución, etc. El alcance se limita a AOV + guardrails observables.
3. **Ventana histórica de 2 años, no un experimento de 2–4 semanas.** Se mitiga restringiendo a
   2017-01/2018-08 y balanceando estacionalidad por diseño, pero el "tiempo en experimento" no es
   realista. La restricción es cosmética, no correctora: el AOV medio apenas cambia (§B6).
4. **Recompra muy baja (3 % de clientes).** Impide una métrica primaria de retención con potencia
   razonable; la retención queda fuera del alcance.
5. **Sesgo de supervivencia en las reseñas.** `review_score` solo existe para pedidos que llegaron a
   generar reseña (99,3 % de cobertura, aceptable) y está sujeto a autoselección del cliente.
6. **Mercado único (Brasil, 2016–2018).** Sin validez externa fuera de ese contexto.

---

## 2.8 Cierre de la Fase 2 y traspaso a la Fase 3

- [x] Procedencia, licencia (CC BY-NC-SA 4.0 **verificada**), tamaño y estructura documentados.
- [x] Métrica primaria perfilada: **AOV media R$ 137,42 · CV 1,523 · skew 9,8**; `log(AOV)` skew 0,24
  / curtosis 0,33 (rango robusto; formalmente no normal pero irrelevante por el TCL a n grande).
- [x] Baseline numérico que faltaba en la Fase 1 → **fijado** (alimenta el power analysis de la Fase 4).
- [x] Guardrails perfilados (G1 4,12/5 · G2 0,63 % · G3 R$ 22,82).
- [x] Unidad de aleatorización caracterizada (97 % de clientes con 1 pedido).
- [x] Preview de potencia: efecto detectable ~+2,7 % (crudo) / ~+2,3 % (winsor.) — **cota superior**,
  no la validación; la validación es la potencia empírica de la Fase 4.
- [x] Limitaciones de validez enumeradas.
- [x] **Auditoría independiente** de Fases 1–2 pasada: sin errores de cálculo, 7 refinamientos
  aplicados (ver `docs/auditoria_fase1_fase2.md`).
- **Siguiente (Fase 3):** aplicar la ventana temporal 2017-01/2018-08, deduplicar reseñas por
  timestamp, deduplicar a 1 pedido/cliente, aplicar winsorización p99,5 (solo contraste), construir
  la tabla analítica `1 fila = 1 cliente-pedido`, simular la asignación y ejecutar el *covariate
  balance check*.
