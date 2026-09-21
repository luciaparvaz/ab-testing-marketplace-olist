# A/B testing en un marketplace — ¿un rediseño de la ficha de producto aumenta el AOV?

> Proyecto de portfolio · metodología **CRISP-DM** · dataset público **Brazilian E-Commerce by Olist**
> Diseño experimental, power analysis, verificación de supuestos, calibración A/A y evaluación de
> decisión de producto sobre un marketplace.

📖 **[`docs/informe_completo.md`](docs/informe_completo.md)** — informe de referencia: recorre cada
fase, cada decisión, los resultados (redacción tipo TFM) y las limitaciones.

🌐 **English version: [`english/README.md`](english/README.md)** — full mirror (docs, code, tests).
This Spanish README is the canonical/reference version; the English one is kept in sync with it.

---

## ⚠️ Nota de honestidad metodológica (léela antes que la decisión de abajo)

El dataset de Olist **no contiene un experimento real**: no hay grupos control/tratamiento ni capa
de tráfico. En este proyecto **la asignación se simula** (50/50 por cliente, semilla fija) y **el
efecto del rediseño se inyecta de forma declarada** — modelo *diluido*: el 20 % de los usuarios
tratados responde con un +25 %, para un efecto medio (ATE) del **+5 %**.

El objetivo **no** es descubrir si el rediseño funciona (lo sabemos, porque el efecto lo ponemos
nosotros), sino **demostrar que el diseño experimental y el análisis estadístico**:

- controlan los falsos positivos (validado sobre 2.000 particiones A/A → tasa 5,0 %, p-valores uniformes),
- recuperan **sin sesgo** un efecto de tamaño conocido (media de 500 réplicas, crudo = 4,97 %; el ATE
  verdadero inyectado es +5,00 %),
- distinguen **significancia estadística** de **relevancia de negocio** — y, más allá de eso,
  **miden la potencia de la propia regla de decisión** (no solo de rechazar H0, ver abajo),
- resisten el **p-hacking** en el análisis por segmentos.

Es el trabajo que hace un equipo de experimentación de producto — y, como cualquier análisis real,
una revisión posterior encontró que dos de sus propias conclusiones no se sostenían del todo (ver
"Hallazgos metodológicos" más abajo). Se corrigieron con código, no solo con texto: la sección
siguiente ya refleja el resultado corregido.

---

## Decisión

**🟡 ITERAR** — el rediseño sube el AOV **+5,7 %** (IC 95 % [+4,0 %, +7,3 %]) de forma muy
significativa, pero **no** supera el umbral de relevancia real de negocio a la escala de este
dataset (ver abajo). No es una decisión de "no funciona": es "funciona, pero no lo suficiente para
justificar el coste del rediseño a este volumen — habría que iterar el diseño o el caso de negocio
antes de invertir".

El MDE de +3 % declarado en la Fase 1 (`docs/01_business_understanding.md`) solo es *break-even*
para un marketplace de **≥ ~415.000 pedidos/año**. El volumen real de este dataset (~58.700
pedidos/año) exige, según el propio modelo de costes del proyecto
([`src/mde_cost_model.py`](src/mde_cost_model.py)), un break-even de **+21,2 %** — muy por encima
tanto del efecto verdadero inyectado (+5 %) como del observado (+5,7 %). Publicar "LANZAR" usando
un impacto en R$ calculado sobre el volumen real, pero un umbral de relevancia pensado para un
marketplace ~7× mayor, era la contradicción que motivó esta corrección (ver `2_impacto_negocio` en
[`outputs/tables/fase5_resumen.json`](outputs/tables/fase5_resumen.json) para el detalle numérico
completo, incluida la decisión que se habría publicado bajo el MDE declarado sin este ajuste).

---

## Resultados por fase de CRISP-DM

| Fase | Contenido | Resultado clave |
|---|---|---|
| **1 · Business Understanding** | Problema, H0/H1, métrica primaria (AOV), guardrails G1–G4, MDE de relevancia (+3 %), regla de decisión | [`docs/01_business_understanding.md`](docs/01_business_understanding.md) |
| **2 · Data Understanding** | Perfilado dirigido; licencia **CC BY-NC-SA 4.0** verificada | AOV media R$ 137 · **CV 1,52 · skew 9,8** · `log(AOV)` casi simétrico |
| **3 · Data Preparation** | Ventana 2017-01/2018-08 · dedup a 1 pedido/cliente · winsor p99,5 solo para el contraste · asignación simulada | 94.703 pedidos-cliente · **balance OK** (\|SMD\| ≤ 0,02) · **SRM OK** (p = 0,64) |
| **4 · Modeling** | Power analysis · supuestos · A/A 2.000 part. · test A/B · A/B multi-semilla (incl. potencia de la regla de decisión) · regresión en guardrail (dos puertas, G1–G4 cuantificados) · efecto heterogéneo · clustered-SE · modelo de costes del MDE | MDE detectable **+2,3 %** · A/A calibrado · dilución **< 1 pp** · MDE +3 % = break-even **solo a ≥ ~415k pedidos/año** |
| **5 · Evaluation** | Significancia vs relevancia (al volumen REAL, no al MDE calibrado para otra escala) · ANCOVA · segmentos + BH · p-hacking | **+5,7 % (winsor) / +6,1 % (crudo)**, ambos significativos pero por debajo del break-even real (+21,2 %) · guardrails intactos · efecto homogéneo → **ITERAR** |
| **6 · Deployment** | Resumen ejecutivo · notebook · README · post LinkedIn | [`docs/resumen_ejecutivo.md`](docs/resumen_ejecutivo.md) · [`notebooks/ab_test_olist.ipynb`](notebooks/ab_test_olist.ipynb) |

### Hallazgos metodológicos del proyecto

- **La potencia de rechazar H0 no es la potencia de la regla de decisión.** El diseño rechaza H0
  casi siempre (potencia empírica ≈ 100 %), pero la puerta "IC 95 % entero por encima del MDE" solo
  se activa en el **~50 % de 500 re-aleatorizaciones** (`8_ab_multiseed` en
  [`outputs/tables/fase4_resumen.json`](outputs/tables/fase4_resumen.json)). El split de este repo
  (`SEED=42`) dio LANZAR bajo el MDE declarado porque se benefició de un desbalance basal favorable
  en la métrica primaria (~+1,2 pp, ahora en la tabla formal de balance, ver más abajo) — no porque
  el diseño esté "sobradamente potenciado" para esa decisión.
- **El MDE de relevancia (+3 %) está derivado, no asertado — y hay que comprobar a qué volumen es
  válido.** Es el *break-even* del rediseño ([`src/mde_cost_model.py`](src/mde_cost_model.py)), pero
  solo para un marketplace con ≥ ~415 k pedidos/año. El impacto en R$ de la Fase 5 se calcula sobre
  el volumen **real** del dataset (~58,7k/año), al que el break-even real es +21,2 %. Publicar
  "LANZAR" mezclando ambas escalas era una contradicción interna del proyecto — la decisión titular
  ahora usa el break-even al volumen real, no el MDE pensado para una escala ~7× mayor.
- **La heterogeneidad del efecto casi no penaliza la potencia** aquí (< 1 pp): la varianza natural
  del AOV (CV ≈ 1,5) domina la que añade concentrar el efecto en el 20 % de usuarios. *Se cuantificó
  por simulación en lugar de asumirlo.*
- **Heterocedasticidad bajo H1** → el efecto diluido infla la varianza del grupo *treatment*
  (Levene p = 1,6·10⁻⁶) → el test primario es **Welch, no Student**.
- **p-hacking demostrado**: probando la magnitud equivocada (lift en R$ en vez de en %) y cortando
  por variables ligadas al tamaño de cesta, aparecen "segmentos ganadores" falsos que **sobreviven
  a Bonferroni**. En la escala correcta (log, efecto relativo), no queda nada. *Corregir por
  multiplicidad no salva un estimando mal planteado.*
- **La winsorización, elegida para reducir varianza, introduce un sesgo puntual de −0,36 pp**
  (verificado con A/B multi-semilla sobre 500 réplicas, con un único cap calculado siempre sobre el
  outcome pre-efecto — [`src/effect_model.py::compute_winsor_cap`](src/effect_model.py), antes había
  tres cálculos de cap distintos e incompatibles). Se reportan crudo (insesgado) y winsor.
- **A n grande, cualquier regresión de guardrail es significativa** → la regla necesita **dos
  puertas** (significativo **Y** magnitud ≥ umbral), no una — incluido G4 (caída de ítems/pedido),
  que antes bloqueaba solo por significancia porque no tenía un umbral de magnitud cuantificado.

---

## Estructura del repositorio

```
├── params.yaml                  # ÚNICA fuente de verdad para los parámetros (seed, alpha, efecto…)
├── run_all.py                   # ÚNICO entrypoint: corre las 6 fases + informe de reproducibilidad
├── data/
│   ├── raw/                     # 9 CSV de Olist (no versionados — ver "Reproducir")
│   └── processed/               # tabla analítica (regenerable)
├── src/
│   ├── config.py                # carga params.yaml + rutas absolutas; nadie más define constantes
│   ├── effect_model.py          # inject_diluted_effect (compartido, sin efectos secundarios)
│   ├── profiling_fase2.py       # Fase 2 — perfilado
│   ├── figures_fase2.py         # Fase 2 — figuras
│   ├── prepare_data.py          # Fase 3 — tabla analítica + asignación simulada
│   ├── balance_check.py         # Fase 3 — covariate balance check + SRM
│   ├── mde_cost_model.py        # Fase 4 — MDE de relevancia derivado de un break-even
│   ├── modeling.py              # Fase 4 — power, supuestos, A/A, A/B, guardrails, multi-semilla…
│   └── evaluation.py            # Fase 5 — decisión, segmentos, p-hacking
├── tests/                       # pytest: config, effect_model, invariantes de los resultados
├── notebooks/
│   ├── ab_test_olist.ipynb      # notebook de PRESENTACIÓN (solo lee outputs/, no calcula)
│   └── ab_test_olist.py         # fuente jupytext (control de versiones)
├── outputs/{figures,tables}/    # figuras + JSON/CSV de resultados (regenerables)
├── docs/                        # informe_completo · 01..06 por fase · 4 auditorías (incl. auditoria_implementacion.md) · resumen ejec. · post LinkedIn
├── requirements.txt · pytest.ini · LICENSE
```

---

## Reproducir

```bash
pip install -r requirements.txt

# datos (no versionados por la licencia CC BY-NC-SA 4.0)
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
#   (o descarga manual desde kaggle.com/datasets/olistbr/brazilian-ecommerce -> data/raw/)

python run_all.py        # ~2 min · corre las 6 fases y VERIFICA los invariantes clave
pytest                   # tests rápidos (config + efecto + invariantes de resultados)
pytest -m slow           # además: re-ejecuta y comprueba idempotencia bit a bit
```

[`run_all.py`](run_all.py) termina con un **informe de reproducibilidad** que comprueba, entre otros:
que la decisión sea una de LANZAR/ITERAR/NO LANZAR con su justificación (no que tenga que ser
"LANZAR" en concreto — un criterio de aceptación fijado sobre el resultado no es falsable, ver
`tests/test_outputs.py::test_decision_consistent_with_real_volume_breakeven`), tasa de falsos
positivos del A/A en [3,5 %; 6,5 %], IC del A/B por encima del MDE, sin SRM, ningún guardrail
degradado — y **sale con código ≠ 0** si algo no cuadra.

### Diseño reproducible

- **Un solo parámetro que tocar:** todo vive en [`params.yaml`](params.yaml), cargado por
  [`src/config.py`](src/config.py). Ningún otro módulo define `SEED`, `ALPHA`, la ventana temporal,
  etc. (hay un test que lo verifica).
- **Un solo entrypoint:** [`run_all.py`](run_all.py) ejecuta las fases en orden de dependencia y
  falla si una no genera sus salidas.
- **Sin rutas de ejecución paralelas:** el notebook **solo lee** [`outputs/`](outputs/); no
  recalcula nada.
- **Rutas absolutas:** funciona desde cualquier directorio de trabajo.
- Semillas fijas → resultado determinista (`pytest -m slow` comprueba idempotencia bit a bit).

---

## Stack

Python · pandas · NumPy · SciPy · statsmodels (`TTestIndPower`, `OLS` con errores HC3,
`multipletests` para Benjamini-Hochberg) · matplotlib · Jupyter / jupytext.

## Datos y licencia

- **Dataset:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  — licencia **CC BY-NC-SA 4.0** (uso no comercial). Los CSV crudos no se incluyen en el repo.
- **Código de este repositorio:** MIT.
