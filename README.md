# A/B testing en un marketplace — ¿un rediseño de la ficha de producto aumenta el AOV?

> Proyecto de portfolio · metodología **CRISP-DM** · dataset público **Brazilian E-Commerce by Olist**
> Diseño experimental, power analysis, verificación de supuestos, calibración A/A y evaluación de
> decisión de producto sobre un marketplace.

**Decisión final: 🟢 LANZAR** — el rediseño sube el AOV **+5,7 %** (IC 95 % [+4,0 %, +7,3 %]), por
encima del umbral de relevancia de negocio (+3 %), sin degradar ningún guardrail.

---

## ⚠️ Nota de honestidad metodológica

El dataset de Olist **no contiene un experimento real**: no hay grupos control/tratamiento ni capa
de tráfico. En este proyecto **la asignación se simula** (50/50 por cliente, semilla fija) y **el
efecto del rediseño se inyecta de forma declarada** — modelo *diluido*: el 20 % de los usuarios
tratados responde con un +25 %, para un efecto medio (ATE) del **+5 %**.

El objetivo **no** es descubrir si el rediseño funciona (lo sabemos, porque el efecto lo ponemos
nosotros), sino **demostrar que el diseño experimental y el análisis estadístico**:

- controlan los falsos positivos (validado sobre 2.000 particiones A/A → tasa 5,0 %, p-valores uniformes),
- recuperan **sin sesgo** un efecto de tamaño conocido (media de 1.000 réplicas = 5,00 %),
- distinguen **significancia estadística** de **relevancia de negocio**,
- resisten el **p-hacking** en el análisis por segmentos.

Es el trabajo que hace un equipo de experimentación de producto.

---

## Resultados por fase de CRISP-DM

| Fase | Contenido | Resultado clave |
|---|---|---|
| **1 · Business Understanding** | Problema, H0/H1, métrica primaria (AOV), guardrails G1–G4, MDE de relevancia (+3 %), regla de decisión | `docs/01_business_understanding.md` |
| **2 · Data Understanding** | Perfilado dirigido; licencia **CC BY-NC-SA 4.0** verificada | AOV media R$ 137 · **CV 1,52 · skew 9,8** · `log(AOV)` casi simétrico |
| **3 · Data Preparation** | Ventana 2017-01/2018-08 · dedup a 1 pedido/cliente · winsor p99,5 solo para el contraste · asignación simulada | 94.703 pedidos-cliente · **balance OK** (\|SMD\| ≤ 0,02) · **SRM OK** (p = 0,64) |
| **4 · Modeling** | Power analysis · supuestos · A/A 2.000 part. · test A/B · A/B multi-semilla · regresión en guardrail · efecto heterogéneo · clustered-SE · modelo de costes del MDE | MDE detectable **+2,3 %** · A/A calibrado · dilución **< 1 pp** · **MDE +3 % = break-even** |
| **5 · Evaluation** | Significancia vs relevancia · ANCOVA · segmentos + BH · p-hacking | **+5,7 % (winsor) / +6,1 % (crudo)**, ambos IC > +3 % · guardrails intactos · efecto homogéneo → **LANZAR** |
| **6 · Deployment** | Resumen ejecutivo · notebook · README · post LinkedIn | `docs/resumen_ejecutivo.md` · `notebooks/ab_test_olist.ipynb` |

### Hallazgos metodológicos del proyecto

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
  (verificado con A/B multi-semilla sobre 500 réplicas). Se reportan crudo (insesgado) y winsor.
- **A n grande, cualquier regresión de guardrail es significativa** → la regla necesita **dos
  puertas** (significativo **Y** magnitud ≥ umbral), no una.
- **El MDE de relevancia (+3 %) está derivado**, no asertado: es el *break-even* del rediseño
  (`src/mde_cost_model.py`), válido para un marketplace con ≥ ~415 k pedidos/año.

---

## Estructura del repositorio

```
├── data/
│   ├── raw/                     # 9 CSV de Olist (no versionados — ver "Reproducir")
│   └── processed/               # tabla analítica (regenerable)
├── src/
│   ├── profiling_fase2.py       # Fase 2 — perfilado
│   ├── prepare_data.py          # Fase 3 — tabla analítica + asignación simulada
│   ├── balance_check.py         # Fase 3 — covariate balance check + SRM
│   ├── modeling.py              # Fase 4 — power, supuestos, A/A, A/B, guardrails, multi-semilla…
│   ├── mde_cost_model.py        # Fase 4 — MDE de relevancia derivado de un break-even
│   └── evaluation.py            # Fase 5 — decisión, segmentos, p-hacking
├── notebooks/
│   ├── ab_test_olist.ipynb      # notebook narrativo reproducible (ejecutado)
│   └── ab_test_olist.py         # fuente jupytext (control de versiones)
├── outputs/
│   ├── figures/                 # f2_*, f3_*, f4_*, f5_*, f_mde_breakeven
│   └── tables/                  # fase{2..5}_resumen.json, transformaciones, balance, srm, segmentos, mde
├── docs/
│   ├── 01_business_understanding.md … 06_deployment.md
│   ├── auditoria_fase1_fase2.md · auditoria_fase5.md · auditoria_global.md
│   ├── resumen_ejecutivo.md
│   └── linkedin_post.md
└── requirements.txt
```

---

## Reproducir

**1. Entorno**

```bash
pip install -r requirements.txt
```

**2. Datos** (no versionados por la licencia CC BY-NC-SA 4.0)

```bash
# opción A — kaggle CLI (requiere token en ~/.kaggle/)
python -m kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip

# opción B — descarga manual desde
# https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
# y descomprimir los 9 CSV en data/raw/
```

**3. Pipeline completo**

```bash
python src/profiling_fase2.py      # Fase 2
python src/prepare_data.py         # Fase 3 — genera data/processed/analytical_table.parquet
python src/balance_check.py        # Fase 3 — balance + SRM
python src/mde_cost_model.py       # Fase 4 — MDE break-even
python src/modeling.py             # Fase 4  (~3-4 min: simulaciones con semilla fija)
python src/evaluation.py           # Fase 5

# o el notebook completo de una vez (~6 min):
jupyter nbconvert --to notebook --execute --inplace notebooks/ab_test_olist.ipynb
```

Todas las semillas están fijadas (`SEED = 42`); los resultados son reproducibles bit a bit.

---

## Stack

Python · pandas · NumPy · SciPy · statsmodels (`TTestIndPower`, `OLS` con errores HC3,
`multipletests` para Benjamini-Hochberg) · matplotlib · Jupyter / jupytext.

## Datos y licencia

- **Dataset:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  — licencia **CC BY-NC-SA 4.0** (uso no comercial). Los CSV crudos no se incluyen en el repo.
- **Código de este repositorio:** MIT.
