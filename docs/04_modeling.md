# Fase 4 — Modeling (diseño estadístico del experimento)

> CRISP-DM · Fase 4 de 6
> Script reproducible: `src/modeling.py` (semillas fijas) → `outputs/tables/fase4_resumen.json`
> Figuras: `outputs/figures/f4_01…04.png`

En CRISP-DM, "Modeling" aquí = **el diseño y la ejecución del contraste estadístico**: power
analysis a priori, verificación de supuestos, calibración A/A y el test A/B con el efecto declarado.

Parámetros declarados (idénticos a §1.7b): `SEED=42`, `α=0,05` bilateral, efecto diluido
`p_resp=0,20`, `δ_resp=0,25` → **ATE = +5 %**, `ε ~ N(0; 0,05)`.
n analítico: **control 47.280 · treatment 47.423**.

---

## 4.1 Power analysis a priori

### Efecto mínimo detectable con n fijo (80 % potencia, α = 0,05 bilateral)

| Métrica | media | CV | **MDE detectable** |
|---|---:|---:|---:|
| AOV crudo | R$ 137,85 | 1,531 | **+2,79 %** |
| AOV winsorizado p99,5 | R$ 134,49 | 1,282 | **+2,34 %** |

Ambos por debajo del **MDE de relevancia de +3 %** (§1.5). La winsorización gana ~0,45 pp de
sensibilidad al comprimir la cola.

### Potencia para el efecto declarado (ATE = +5 %)

| | efecto uniforme (fórmula) | efecto diluido (simulado, 1.000 réplicas) |
|---|---:|---:|
| Potencia (AOV crudo) | 0,999 | **1,000** |
| Potencia (AOV winsor) | 1,000 | **1,000** |
| Lift medio estimado | — | **4,999 %** (crudo) / **5,006 %** (winsor) |
| Sesgo del estimador | — | **≈ 0 pp** |

→ El diseño está **sobradamente potenciado** para +5 % y el estimador es **insesgado**.

### ¿Penaliza la potencia el efecto diluido? (`f4_04_power_vs_n.png`)

Predicción de §1.7b: concentrar el efecto en el 20 % infla la varianza del *treatment* y baja la
potencia. **Verificado por simulación en una rejilla de n (400 → 47.280 por grupo):**

| n / grupo | potencia uniforme | potencia diluida | penalización |
|---:|---:|---:|---:|
| 400 | 0,08 | 0,11 | ~0 pp (ruido) |
| 3.200 | 0,26 | 0,25 | +0,7 pp |
| 12.800 | 0,74 | 0,74 | +0,5 pp |
| 47.280 | 1,00 | 1,00 | −0,1 pp |

**Conclusión:** la penalización es **< 1 pp en todo el rango** — despreciable. Motivo: la varianza
que añade la dilución (≈ `p·(1−p)·δ_resp²·E[X²]` ≈ 1,4 % de la varianza total) es minúscula frente
a la **varianza natural del AOV** (CV ≈ 1,5). La intuición es correcta en dirección pero
**irrelevante en magnitud** aquí. *Hallazgo del proyecto: cuantificar supera a asumir.*

---

## 4.2 Verificación de supuestos (`f4_01_tcl_normalidad.png`)

| Supuesto | Prueba | Resultado | Veredicto |
|---|---|---|---|
| Normalidad de los **datos** | D'Agostino K² | K² = 5.453, p ≈ 0 | **No normal** (esperado — skew 9,8) |
| Normalidad de la **media** (TCL) | D'Agostino K² sobre 5.000 medias bootstrap (n = 47 k) | K² = 0,38, **p = 0,826** | **Compatible con normal → Welch-t válido** |
| Homocedasticidad **sin efecto** (A/A) | Levene (centrado en mediana) | stat = 1,61, p = 0,205 | Varianzas iguales (esperado) |
| Homocedasticidad **con efecto diluido** | Levene | stat = 22,97, **p = 1,6·10⁻⁶** | El efecto **infla la varianza del treatment** → **usar Welch, NO Student** |
| Independencia | por diseño | asignación aleatoria + dedup a 1 pedido/cliente | Sin correlación intra-cliente; SUTVA asumido |

**El test primario es la t de Welch** (no la de Student): la verificación muestra que bajo H1 las
varianzas de grupo **no** son iguales, exactamente el caso para el que Welch está diseñado.

---

## 4.3 Calibración A/A — 2.000 particiones aleatorias

Para cada una de 2.000 particiones 50/50 (sin efecto), Welch-t sobre la métrica y registro del
p-valor. Criterio: IC 95 % de la tasa de falsos positivos contiene 0,05 **y** p-valores uniformes
(Kolmogórov–Smirnov).

| Métrica | Falsos positivos (α = 0,05) | IC 95 % | KS vs. uniforme (p) | Veredicto |
|---|---:|---:|---:|:--:|
| AOV crudo | **4,95 %** | [3,99 %; 5,91 %] | 0,53 | ✅ calibrado |
| AOV winsor p99,5 | **5,00 %** | [4,04 %; 5,96 %] | 0,93 | ✅ calibrado |
| log(AOV) | **5,00 %** | [4,04 %; 5,96 %] | 0,72 | ✅ calibrado |

Ver `f4_02_aa_pvalores.png` (histograma plano de p-valores). **El pipeline no genera falsos
positivos y los p-valores están calibrados.** (Nota: una corrida previa a 1.000 réplicas dio KS
p = 0,044 para la variante winsorizada; se verificó sobre múltiples semillas que es ruido —la tasa
de falsos positivos se mantiene en ~5 %— y a 2.000 réplicas desaparece.)

---

## 4.4 Test A/B — efecto diluido inyectado en la asignación declarada (SEED = 42)

`f4_03_ab_efecto.png`

| Test | lift AOV | IC 95 % | p-valor | ¿+5 % en IC? |
|---|---:|---:|---:|:--:|
| **Welch · AOV winsor p99,5 (primario)** | **+5,67 %** | **[+3,99 %; +7,34 %]** | **3,1·10⁻¹¹** | ✅ |
| Welch · AOV crudo | +6,11 % | [+4,09 %; +8,13 %] | 3,1·10⁻⁹ | ✅ |
| Bootstrap (10.000, sin supuestos) | — | [+4,05 %; +8,19 %] | — | ✅ |
| log · cociente de medias geométricas | +4,79 % | — | 1,4·10⁻¹⁴ | (otra métrica) |
| Mann–Whitney (dominancia estocástica) | — | — | 1,8·10⁻¹⁵ | (otra métrica) |

**Todos los intervalos contienen el efecto verdadero (+5 %).** El estimador puntual queda por encima
del 5 % porque **este split concreto tiene +1,2 % de desbalance basal** (Fase 3, no significativo,
p = 0,235): el efecto inyectado sobre el *treatment* es +4,86 %, y +4,86 % × (1 + 1,2 %) ≈ +6,1 %.
Sobre 1.000 réplicas el estimador es **insesgado** (media 5,00 %) — cualquier experimento único
arrastra el ruido de su asignación, de ahí que la decisión se ancle en el **IC**, no en el punto.

### Guardrails (Welch / z de proporciones · corrección Benjamini–Hochberg · sin efecto inyectado)

| Guardrail | control | treatment | p bruto | **p ajustado (BH)** | ¿Degradado? |
|---|---:|---:|---:|---:|:--:|
| G1 · review_score | 4,114 | 4,116 | 0,80 | 0,80 | ❌ no |
| G2 · tasa de cancelación | 0,541 % | 0,570 % | 0,56 | 0,77 | ❌ no |
| G3 · freight_value | R$ 22,74 | R$ 22,89 | 0,30 | 0,77 | ❌ no |
| G4 · nº de ítems | 1,140 | 1,138 | 0,58 | 0,77 | ❌ no |

**Ningún guardrail se degrada** (ningún p ajustado < 0,05). Es el resultado esperado: el diseño solo
inyecta efecto en la métrica primaria. *(Extensión natural: inyectar una regresión sub-umbral en G1
y comprobar que el diseño la detecta o la deja pasar según el umbral de alarma.)*

---

## 4.5 Barrido de decisión — las tres ramas de la regla §1.5

Aplicando la regla lanzar / iterar / no lanzar a distintos tamaños de efecto inyectado
(métrica primaria winsorizada, guardrails OK, split SEED = 42 con +1,2 % de desbalance basal):

| ATE inyectado | lift observado | IC 95 % | p-valor | **Decisión** |
|---:|---:|---:|---:|:--:|
| 0 % | +1,01 % | [−0,63 %; +2,65 %] | 0,227 | **NO LANZAR** |
| 1 % | +1,95 % | [+0,30 %; +3,60 %] | 0,020 | **ITERAR** |
| 2 % | +2,89 % | [+1,23 %; +4,54 %] | 6·10⁻⁴ | **ITERAR** |
| 3 % | +3,82 % | [+2,16 %; +5,48 %] | 6·10⁻⁶ | **ITERAR** |
| 4 % | +4,75 % | [+3,08 %; +6,41 %] | 2·10⁻⁸ | **LANZAR** |
| **5 % (declarado)** | **+5,67 %** | **[+3,99 %; +7,34 %]** | **3·10⁻¹¹** | **LANZAR** |
| 8 % | +8,40 % | [+6,71 %; +10,09 %] | 2·10⁻²² | **LANZAR** |

El diseño **alcanza las tres decisiones**: un efecto real pero por debajo del umbral de relevancia
(ATE ≤ 3 %) produce "ITERAR" —significativo pero con el IC tocando el MDE—, y solo a partir de un
efecto claramente relevante se dispara "LANZAR".

---

## 4.6 Cierre de la Fase 4 y traspaso a la Fase 5

- [x] Power analysis a priori: MDE detectable +2,79 % / +2,34 %; potencia ~100 % para +5 %;
  estimador insesgado; **penalización por dilución < 1 pp (despreciable, cuantificado)**.
- [x] Supuestos verificados: normalidad de la media por TCL (p = 0,83), heterocedasticidad bajo H1
  → **Welch justificado**, independencia por diseño.
- [x] Calibración A/A (2.000 particiones): falsos positivos 5,0 %, p-valores uniformes (KS p ≥ 0,5).
- [x] Test A/B: **+5,67 % [+3,99 %; +7,34 %], p = 3·10⁻¹¹**; IC contiene el +5 % real.
- [x] Guardrails con BH: **ninguno degradado**.
- [x] Barrido de decisión: las tres ramas de la regla son alcanzables.
- **Siguiente (Fase 5 — Evaluation):** traducir a decisión de producto (significancia vs.
  relevancia frente al MDE), análisis por segmentos (con control de p-hacking), y conclusión
  lanzar / iterar / no lanzar.
