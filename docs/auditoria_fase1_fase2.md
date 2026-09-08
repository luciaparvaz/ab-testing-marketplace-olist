# Auditoría — Fases 1 y 2 (código, resultados e interpretaciones)

> Revisión crítica previa al cierre de fases y a los commits.
> Método: re-derivación independiente de todos los números clave por una segunda vía
> (`/tmp/audit_fase2.py`, reproducible), revisión de supuestos y búsqueda de errores.
> Veredicto global: **sin errores materiales de cálculo**. 7 refinamientos de interpretación/decisión
> antes de la Fase 3. 1 decisión de diseño de la simulación que sigue abierta.

---

## A. Verificación de cálculos — todo cuadra

| Número (Fase 2) | Valor en el doc | Re-derivación independiente | ¿OK? |
|---|---|---|---|
| n pedidos válidos | 98.199 | 98.199 | ✅ |
| AOV media / mediana | R$ 137,42 / 86,90 | R$ 137,4189 / 86,90 | ✅ |
| AOV σ / CV | 209,31 / 1,523 | 209,3064 / 1,5231 | ✅ |
| AOV skew / curtosis | 9,77 / 271 | 9,772 / 271,4 | ✅ |
| log(AOV) skew / curtosis | 0,24 / 0,33 | 0,2424 / 0,3346 | ✅ |
| Lift detectable 80 % | +2,72 % | +2,723 % (statsmodels **y** fórmula cerrada coinciden) | ✅ |
| % clientes con 1 pedido | 96,96 % | 96,96 % | ✅ |

**Chequeos de integridad que pasan:**

- `order_items.price` no tiene ceros ni negativos (mín R$ 0,85); 1 fila = 1 unidad → la suma por
  `order_id` es el valor de mercancía correcto.
- **El *gotcha* de Olist está bien resuelto:** `orders.customer_id` es único por pedido (99.441),
  `customer_unique_id` identifica a la persona (96.096). El perfilado usa `customer_unique_id` para
  contar clientes y para la unidad de aleatorización. Correcto.
- `freight_value ≥ 0` siempre.

---

## B. Refinamientos de interpretación (antes de Fase 3)

### B1. "log(AOV) casi normal" — matizar

La transformación log baja el skew de 9,8 a **0,24** y la curtosis de 271 a **0,33**. Pero el test
de **D'Agostino sobre `log(AOV)` (n = 5.000) rechaza la normalidad con p ≈ 8·10⁻²⁴**.

- **No es un error**, es una precisión: a n grande, cualquier desviación mínima "es significativa".
- **Redacción corregida:** *"la transformación log lleva la asimetría y la curtosis a un rango
  (skew 0,24; curtosis 0,33) en el que el t-test es robusto; formalmente sigue sin ser normal
  (D'Agostino p < 10⁻²⁰ a n = 5.000), pero eso es irrelevante porque con n ≈ 49 k/grupo la
  distribución muestral de la media es normal por el TCL con independencia del skew"*.

### B2. El test en escala log responde a **otra** pregunta de negocio

- t-test sobre **AOV bruto** → contrasta la **media aritmética** → es lo que determina el revenue
  total (revenue = media × volumen). **Es la métrica de negocio.**
- t-test sobre **log(AOV)** → contrasta la media de los logs → equivale al **cociente de medias
  geométricas** ≈ desplazamiento de la **mediana**. **No es** el AOV.
- **Consecuencia:** el análisis en log entra como **robustez**, no como "versión con más potencia"
  del primario. Que detecte +1,7 % en vez de +2,7 % no es una ventaja: mide un efecto distinto.
- Se corrige el doc de Fase 2 para no sugerir que log = más potencia "gratis".

### B3. Clientes recurrentes — simplificar el diseño

La auditoría cuantifica el impacto real de los clientes con varios pedidos:

| Enfoque | n | AOV media |
|---|---:|---:|
| Todos los pedidos | 98.199 | R$ 137,42 |
| 1 pedido por cliente (el primero) | 94.983 | R$ 137,90 |

Diferencia de media: **−0,35 %**. Insignificante.

- **Recomendación revisada:** en lugar de "errores estándar por clúster de cliente" (más complejo),
  **deduplicar a 1 pedido por cliente (el primero en la ventana)**. Así **unidad de aleatorización =
  unidad de análisis**, desaparece la necesidad de SE por clúster, y el coste es 3,3 % de pedidos y
  0,35 % de sesgo en la media. Más limpio y más fácil de explicar a un stakeholder.
- Alternativa igualmente válida: conservar todos los pedidos + SE por clúster. Se elige la simple.

### B4. Winsorización — cuantificada, con su efecto colateral

| Cap | Umbral | % obs recortadas | CV | Lift detectable 80 % | AOV media resultante |
|---|---:|---:|---:|---:|---:|
| sin cap | R$ 13.440 | 0 % | 1,523 | 2,72 % | R$ 137,42 |
| **p99,5** | **R$ 1.350** | **0,50 %** | **1,278** | **2,28 %** | **R$ 134,11** |
| p99 | R$ 995 | 1,00 % | 1,181 | 2,11 % | R$ 131,55 |
| p97,5 | R$ 626 | 2,50 % | 1,019 | 1,82 % | R$ 125,63 |

- La ganancia de potencia de winsorizar a p99,5 es **modesta** (2,72 → 2,28 %).
- **Efecto colateral:** winsorizar a p99,5 **baja la media un 2,4 %** (R$ 137,42 → 134,11). Para un
  contraste de **diferencia** entre grupos da igual (ambos grupos se winsorizan igual), pero el
  **AOV base que se reporta descriptivamente** debe ser el **bruto (R$ 137,42)**.
- **Decisión revisada:** winsorizar a **p99,5 solo para el contraste**; reportar el AOV base
  descriptivo **sin winsorizar**; incluir el análisis **sin winsorizar** como robustez. Criterio
  pre-registrado aquí, antes de ver ningún resultado del test.

### B5. Deduplicación de reseñas — por timestamp, no por orden de fila

- 551 pedidos tienen >1 reseña. Deduplicar "por última fila del CSV" vs. "por
  `review_answer_timestamp` más reciente" **cambia el score en 100 pedidos**.
- Impacto en la media global: **nulo** (4,0867 vs 4,0864).
- Aun así, la Fase 3 deduplicará **por timestamp** (criterio principista). El perfilado de Fase 2 no
  se rehace: el número de guardrail G1 (4,12 sobre pedidos válidos) no cambia de forma relevante.

### B6. Ventana temporal — es cosmética, no corrige un sesgo

- AOV media ventana completa: R$ 137,42 · ventana 2017-01/2018-08: **R$ 137,37** (n 98.199 → 97.905).
- Restringir la ventana **no cambia la media** ni introduce/corrige sesgo. Se mantiene la restricción
  **solo por realismo** (que la duración se parezca a un experimento real) y para quitar meses
  residuales — no como paso de corrección. El doc de Fase 2 se ajusta para no sobrevender esto.
- Nota lateral: 2017-01 tiene AOV alto (R$ 152) sobre solo 787 pedidos (early adopters). Irrelevante
  tras la asignación aleatoria.

### B7. Detalle menor

- `payment_value` está disponible para 98.198 de 98.199 pedidos válidos (1 pedido `delivered` sin
  registro de pago). Se documenta; no afecta a la métrica primaria (que sale de `order_items`).

---

## C. Auditoría de las interpretaciones de alto nivel

| Afirmación en los docs | Veredicto de la auditoría |
|---|---|
| "La muestra tiene potencia suficiente para detectar el MDE de +3 %" | **Frágil tal cual.** El margen es +2,72 % vs +3 %: 0,3 pp. Con winsorización p99,5 pasa a +2,28 % (más holgado). **Corrección:** enmarcar la conclusión en la **potencia alcanzada al δ = 5 % inyectado** (Fase 4/5) y presentar el +2,7 % como "cota superior del efecto detectable en el peor caso (datos crudos)". El **test A/A de la Fase 4 es la validación real** de la calibración, no este preview analítico. |
| "t de Welch sobre AOV bruto es test primario defendible" | **Correcto**, por el TCL a n ≈ 49 k/grupo. Se refuerza con la simulación A/A (comprueba empíricamente el error tipo I). |
| "Estacionalidad balanceada por diseño" | **Correcto** — la asignación aleatoria por cliente reparte los meses por igual. Confirmado además que la media de AOV es estable entre ventanas. |
| Corrección BH sobre guardrails, primario excluido | **Estándar y correcto.** Añadir: los análisis por segmento de la Fase 5 son **exploratorios/no confirmatorios** y se etiquetan como tales (ya recogido en §1.6). |
| "El proyecto demuestra rigor de diseño, no un hallazgo de negocio" | **Correcto y bien señalado** en §2.7 y §1.7. Es la limitación central y está declarada de forma prominente. |

---

## D. Decisión de diseño ABIERTA — forma funcional del efecto sintético (Fase 4)

El usuario eligió "efecto sintético declarado". La **forma** del efecto sigue sin fijarse. Opciones:

| Opción | Modelo | Realismo respecto a "cross-sell + barra de envío gratis" | Implicación estadística |
|---|---|---|---|
| **(a) Multiplicativo uniforme** | `aov_T = aov_C · (1 + δ + ε)` | Bajo: asume que todos los pedidos crecen el mismo % | La más simple; encaja directo con un MDE en % |
| **(b) Diluido** | solo una fracción `p` de los tratados responde (p. ej. 25 %), el resto sin cambio | **Alto:** un rediseño solo mueve a parte de los usuarios | Estresa el power analysis (el efecto medio se diluye); más instructivo |
| **(c) Aditivo por ítem** | con prob. `q`, se añade 1 ítem recomendado de valor ~ distribución real de `price` | **Alto** para el cross-sell | El efecto absoluto no es constante en % → interesante para comparar test en nivel vs en % |
| **(d) Concentrado en umbral** | empuja hacia arriba solo pedidos en una banda por debajo del umbral de envío gratis | **Alto** para la barra de progreso | Efecto muy heterogéneo; complejo de calibrar |

**Recomendación:** **(b) diluido** con `δ_respondedores` tal que el efecto medio global sea 5 %
(p. ej. 20 % responde con +25 %). Es realista, mantiene el δ medio declarado y hace el power
analysis y el A/A más informativos. **(a)** si se prioriza máxima simplicidad y encaje con el
timeline.

---

## E. Cambios a aplicar antes de Fase 3 (resumen accionable)

1. Editar `docs/02_data_understanding.md`: matizar "casi normal" (B1), quitar la idea de que log =
   más potencia (B2), reformular el enfoque de recurrentes hacia dedup 1/cliente (B3), reescribir la
   decisión de winsorización con su efecto en la media (B4), suavizar la justificación de la ventana
   temporal (B6), añadir la nota de `payment_value` (B7).
2. Editar `docs/01_business_understanding.md`: §1.3 (dedup 1/cliente en vez de SE por clúster),
   §1.5 (enmarcar potencia en el δ inyectado, no en el margen +2,7/+3), §1.7 (fijar la forma del
   efecto según decisión de D).
3. Ninguna reejecución de perfilado es necesaria: los números de Fase 2 son correctos.
4. Fase 3 incorpora: dedup reseñas por timestamp, dedup a 1 pedido/cliente, winsorización p99,5
   declarada, ventana 2017-01/2018-08.

---

## F. Resolución (decisiones del usuario)

1. **Forma del efecto sintético:** opción **(b) diluida** — `p_resp = 0,20`, `δ_resp = 0,25`,
   ATE = +5 %. Fijada en `docs/01_business_understanding.md` §1.7b.
2. **Recurrentes:** **dedup a 1 pedido/cliente** (el primero de la ventana). Robustez con todos los
   pedidos + SE por clúster. Fijada en §1.3 y §2.5.
3. Cambios E1–E2 **aplicados** a los docs de Fase 1 y 2. Procede el commit de Fases 1 + 2 +
   auditoría y el arranque de la Fase 3.
