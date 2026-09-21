# Resumen ejecutivo — Test A/B del rediseño de la ficha de producto

**Proyecto:** experimentación de producto en un marketplace (dataset público Brazilian E-Commerce
by Olist) · **Metodología:** CRISP-DM · **Fecha:** 2026

---

## Nota metodológica (léela primero — condiciona todo lo demás en este documento)

> Este es un **proyecto de portfolio** construido sobre un dataset público que **no contiene un
> experimento real**. La división en grupos control/tratamiento y el efecto del rediseño están
> **simulados y declarados** (efecto medio +5 %, concentrado en el 20 % de los usuarios que
> responden). Por tanto, **este informe no describe un hallazgo real sobre Olist**: demuestra que
> el **proceso de diseño, análisis y decisión** es correcto —controla los falsos positivos
> (validado sobre 2.000 particiones aleatorias), recupera sin sesgo un efecto de tamaño conocido, y
> distingue la significancia estadística de la relevancia de negocio—. Es exactamente el trabajo
> que hace un equipo de experimentación de producto — incluida la parte de revisar las propias
> conclusiones: una revisión posterior de este proyecto encontró que la primera versión de este
> documento recomendaba "LANZAR" mezclando dos escalas de negocio incompatibles (ver "La
> decisión" más abajo); se corrigió con código, no solo reescribiendo el texto.

## La pregunta de negocio

El equipo de Producto propone un **rediseño de la ficha de producto** —recomendaciones de
"productos que suelen comprarse juntos" (*cross-sell*) más una barra de progreso hacia el envío
gratuito—. La hipótesis: los clientes añadirán artículos y **subirá el valor medio del pedido
(AOV)**, sin que empeoren la satisfacción ni las cancelaciones.

**¿Debe lanzarse el cambio a todos los usuarios?**

## Cómo se decidió (antes de ver ningún dato)

| | |
|---|---|
| **Métrica de éxito** | Valor medio del pedido (AOV) |
| **Métricas de control** ("guardrails") | Puntuación de reseña, tasa de cancelación, coste de envío, nº de artículos por pedido |
| **Umbral de relevancia declarado** | El AOV debe subir **al menos un +3 %** para que el cambio compense su coste de desarrollo y mantenimiento (cifra obtenida de un modelo de break-even) — **pero ese +3 % solo es correcto para un marketplace con ≥ ~415.000 pedidos/año**, un dato que no se cruzó con el volumen real hasta esta revisión (ver "La decisión") |
| **Regla** | **Lanzar** solo si la mejora es estadísticamente sólida **y** su intervalo de confianza está entero por encima del umbral de relevancia **que corresponde al volumen real** **y** ningún guardrail se degrada |

## El resultado

| | |
|---|---|
| **Efecto sobre el AOV** | **+5,7 %** (intervalo de confianza al 95 %: **+4,0 % a +7,3 %**); estimación entre +5,7 % y +6,1 % según el tratamiento de valores extremos |
| **Solidez estadística** | Muy alta (p ≈ 0,00000000003); confirmada con cinco métodos alternativos y con 500 repeticiones del experimento — pero "significativo" no es lo mismo que "activa la regla de lanzamiento": ver más abajo |
| **Guardrails** | **Ninguno se degrada** (satisfacción, cancelaciones, envío y tamaño de cesta se mantienen; el umbral de tamaño de cesta ya tiene magnitud cuantificada, antes bloqueaba solo por significancia) |
| **¿Funciona mejor en algún segmento?** | No: el efecto relativo es **homogéneo** entre tipo de pago, región, categoría, tamaño de cesta y trimestre |
| **Volumen del dataset** | ~58.700 pedidos/año — el volumen **real** sobre el que se calcula el impacto económico de abajo |
| **Impacto económico estimado** | **+R$ 456.000 al año** de valor de mercancía (intervalo: +R$ 322.000 a +R$ 591.000); ≈ **+R$ 68.000 al año** de ingreso por comisión — **frente a un coste del rediseño de ~R$ 410.000 a 2 años**: a este volumen, el margen esperado no cubre claramente el coste |

## La decisión

# 🟡 ITERAR (no LANZAR)

El efecto es real, positivo y estadísticamente muy sólido — pero **no supera el umbral de
relevancia que corresponde al volumen real de este dataset**. El +3 % declarado en la fase de
diseño de negocio es el break-even correcto solo para un marketplace ~7× mayor
(≥ ~415.000 pedidos/año); al volumen real (~58.700 pedidos/año), el propio modelo de costes del
proyecto exige un break-even de **+21,2 %**, muy por encima tanto del efecto verdadero (+5 %) como
del observado (+5,7 %). Con la regla de decisión aplicada correctamente al volumen real, la
recomendación es **iterar** — sobre el diseño (buscar un efecto mayor) o sobre el caso de negocio
(reducir el coste de desarrollo/mantenimiento, o validar esto en un marketplace de mayor volumen)
— no desplegar al 100 % del tráfico todavía.

*(Bajo el MDE declarado sin este ajuste de volumen, la decisión habría sido "LANZAR" — así se
publicó en una versión anterior de este mismo documento. Es la contradicción que esta revisión
corrigió: el detalle numérico completo, con ambas decisiones, está en `2_impacto_negocio` de
[`outputs/tables/fase5_resumen.json`](../outputs/tables/fase5_resumen.json).)*

## Un segundo hallazgo de esta revisión: la potencia de la regla, no solo la del test

Además del punto anterior, repetir el experimento completo 500 veces (re-split + re-inyección del
efecto) muestra que la puerta "IC 95 % entero por encima del MDE declarado (+3 %)" solo se activa
en **~50 % de las re-aleatorizaciones** — aunque el test rechaza H0 casi siempre (potencia ≈ 100 %).
El split concreto de este repositorio (semilla fija) dio un resultado favorable en parte porque el
grupo tratamiento partía, por azar, con un AOV basal ~1,2 % más alto que el control (ahora medido y
declarado, no solo observado). Ninguna de las dos correcciones cambia el diseño del experimento en
sí — lo que cambia es qué conclusión de negocio es consistente con ese diseño.

## Qué vigilar si se decide iterar y relanzar

- Si se reduce el coste de desarrollo/mantenimiento o se valida a mayor volumen: repetir este mismo
  análisis con el break-even recalculado a la nueva escala.
- El AOV real frente al break-even que corresponda al volumen de despliegue real, no al +3 %
  genérico.
- La tasa de devoluciones y de reclamaciones (no medibles en este dataset; sí en producción).
- Que el efecto no se diluya por novedad: revisar de nuevo a los 90 días si llega a desplegarse.

---

*Documentación completa por fase de CRISP-DM y auditorías estadísticas en el repositorio.*
