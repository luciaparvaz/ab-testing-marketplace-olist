# Resumen ejecutivo — Test A/B del rediseño de la ficha de producto

**Proyecto:** experimentación de producto en un marketplace (dataset público Brazilian E-Commerce
by Olist) · **Metodología:** CRISP-DM · **Fecha:** 2026

---

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
| **Umbral de relevancia** | El AOV debe subir **al menos un +3 %** para que el cambio compense su coste de desarrollo y mantenimiento (cifra obtenida de un modelo de break-even; válida para el volumen de pedidos de un marketplace de tamaño medio-grande) |
| **Regla** | **Lanzar** solo si la mejora es estadísticamente sólida **y** su intervalo de confianza está entero por encima del +3 % **y** ningún guardrail se degrada |

## El resultado

| | |
|---|---|
| **Efecto sobre el AOV** | **+5,7 %** (intervalo de confianza al 95 %: **+4,0 % a +7,3 %**); estimación entre +5,7 % y +6,1 % según el tratamiento de valores extremos |
| **Solidez estadística** | Muy alta (p ≈ 0,00000000003); confirmada con cinco métodos alternativos y con 500 repeticiones del experimento |
| **Guardrails** | **Ninguno se degrada** (satisfacción, cancelaciones, envío y tamaño de cesta se mantienen) |
| **¿Funciona mejor en algún segmento?** | No: el efecto relativo es **homogéneo** entre tipo de pago, región, categoría, tamaño de cesta y trimestre |
| **Impacto económico estimado** | **+R$ 456.000 al año** de valor de mercancía (intervalo: +R$ 322.000 a +R$ 591.000); ≈ **+R$ 68.000 al año** de ingreso por comisión |

## La decisión

# 🟢 LANZAR

La mejora del AOV es estadísticamente sólida, **materialmente relevante** (todo el intervalo de
confianza supera el umbral de +3 % fijado por negocio) y **no tiene coste** en ninguna métrica de
control. Se recomienda desplegar el rediseño al 100 % del tráfico y monitorizar el AOV y los
guardrails durante las cuatro semanas siguientes.

## Qué vigilar tras el lanzamiento

- El AOV real a 4 semanas frente al **+3 % mínimo** esperado.
- La tasa de devoluciones y de reclamaciones (no medibles en este dataset; sí en producción).
- Que el efecto no se diluya por novedad: revisar de nuevo a los 90 días.

---

## Nota metodológica (imprescindible)

> Este es un **proyecto de portfolio** construido sobre un dataset público que **no contiene un
> experimento real**. La división en grupos control/tratamiento y el efecto del rediseño están
> **simulados y declarados** (efecto medio +5 %, concentrado en el 20 % de los usuarios que
> responden). Por tanto, **este informe no describe un hallazgo real sobre Olist**: demuestra que
> el **proceso de diseño, análisis y decisión** es correcto —controla los falsos positivos
> (validado sobre 2.000 particiones aleatorias), recupera sin sesgo un efecto de tamaño conocido, y
> distingue la significancia estadística de la relevancia de negocio—. Es exactamente el trabajo
> que hace un equipo de experimentación de producto.

*Documentación completa por fase de CRISP-DM y auditorías estadísticas en el repositorio.*
