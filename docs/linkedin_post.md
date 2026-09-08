# Borrador — Post de LinkedIn

*(tono personal, en español; adaptar a inglés si el público objetivo es Berlín internacional.
~230 palabras. Añadir 2–3 imágenes: forest plot de segmentos, curva de potencia, y el love-plot
de balance.)*

---

Acabo de terminar un proyecto de **A/B testing en un marketplace** y me quedo con una lección que
no esperaba.

**El contexto:** simulé el test de un rediseño de ficha de producto (cross-sell + barra de envío
gratis) sobre datos públicos de e-commerce, siguiendo CRISP-DM de punta a punta: hipótesis, métrica
primaria, guardrails, cálculo de potencia, y una regla de decisión escrita **antes** de mirar los
datos.

**La parte interesante fue el análisis por segmentos.** El efecto que inyecté era homogéneo: el
mismo % de subida para todos. Aun así, si medía el impacto en **valor absoluto (R$)** y cortaba los
datos por variables correlacionadas con el tamaño del pedido, "encontraba" segmentos donde el
efecto era claramente mayor... y esos falsos hallazgos **sobrevivían incluso a la corrección de
Bonferroni**.

La causa: un efecto multiplicativo genera automáticamente más euros de subida en las cestas
grandes. No era heterogeneidad real, era un artefacto de medir la magnitud equivocada.

**La moraleja:** corregir por comparaciones múltiples no te salva si el *estimando* está mal
planteado. Hay que testar la pregunta de negocio correcta (¿cambia el **%**?), no la que primero
sale del `groupby`.

Todo el código, la documentación por fase y dos auditorías estadísticas están en el repo 👇

#DataScience #ABTesting #Experimentation #ProductAnalytics #CRISPDM

---

## Variante corta (para X / Bluesky, ~110 palabras)

Proyecto nuevo: A/B testing de un rediseño de e-commerce, CRISP-DM completo.

Lo que más me sorprendió: con un efecto **homogéneo** por construcción, medir el impacto en R$
absolutos (en vez de en %) y cortar por variables ligadas al tamaño de cesta producía "segmentos
ganadores" falsos que **sobrevivían a Bonferroni**.

Un efecto multiplicativo da más euros de subida en pedidos grandes → parece heterogéneo, pero no lo
es.

Corregir por multiplicidad no arregla un estimando mal elegido. Repo con código + auditorías 👇
