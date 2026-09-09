"""
Prepara el proyecto para NotebookLM.

NotebookLM acepta: Markdown (.md), texto (.txt), PDF, Google Docs/Slides, URLs, YouTube.
NO acepta directamente: .ipynb, .py, .csv, .json, .png.

Este script genera, en notebooklm/:
  - copias numeradas de README + docs/*.md               (subir tal cual)
  - 80_codigo_fuente.md   : todos los src/*.py en bloques (subir tal cual)
  - 85_resultados_numericos.md : JSON/CSV de outputs como tablas legibles
  - 90_notebook_ejecutado.md   : el notebook con código y salidas (ya generado por nbconvert)
  - 95_figuras.pdf        : todas las figuras en un PDF, una por página con su pie
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path

try:
    import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notebooklm"
OUT.mkdir(exist_ok=True)

# --- 1. copiar README + docs en orden de lectura --------------------------
DOC_ORDER = [
    ("00_README.md", ROOT / "README.md"),
    ("03_informe_completo.md", ROOT / "docs/informe_completo.md"),
    ("05_resumen_ejecutivo.md", ROOT / "docs/resumen_ejecutivo.md"),
    ("10_fase1_business_understanding.md", ROOT / "docs/01_business_understanding.md"),
    ("20_fase2_data_understanding.md", ROOT / "docs/02_data_understanding.md"),
    ("30_fase3_data_preparation.md", ROOT / "docs/03_data_preparation.md"),
    ("40_fase4_modeling.md", ROOT / "docs/04_modeling.md"),
    ("50_fase5_evaluation.md", ROOT / "docs/05_evaluation.md"),
    ("60_fase6_deployment.md", ROOT / "docs/06_deployment.md"),
    ("70_auditoria_fase1_fase2.md", ROOT / "docs/auditoria_fase1_fase2.md"),
    ("72_auditoria_fase5.md", ROOT / "docs/auditoria_fase5.md"),
    ("74_auditoria_global.md", ROOT / "docs/auditoria_global.md"),
    ("99_linkedin_post.md", ROOT / "docs/linkedin_post.md"),
]
for dst, src in DOC_ORDER:
    shutil.copyfile(src, OUT / dst)
    print("copiado", dst)

# --- 2. código fuente en un solo .md -------------------------------------
CODE_FILES = [("params.yaml", "yaml"), ("run_all.py", "python"),
              ("src/config.py", "python"), ("src/effect_model.py", "python"),
              ("src/profiling_fase2.py", "python"), ("src/figures_fase2.py", "python"),
              ("src/prepare_data.py", "python"), ("src/balance_check.py", "python"),
              ("src/mde_cost_model.py", "python"), ("src/modeling.py", "python"),
              ("src/evaluation.py", "python"),
              ("tests/test_config.py", "python"), ("tests/test_effect_model.py", "python"),
              ("tests/test_outputs.py", "python"), ("tests/test_reproducibility.py", "python")]
parts = ["# Código fuente del proyecto\n",
         "`params.yaml` = única fuente de verdad de los parámetros · `run_all.py` = único "
         "entrypoint · `src/` = una fase de CRISP-DM por fichero · `tests/` = pytest.\n"]
for rel, lang in CODE_FILES:
    fp = ROOT / rel
    if not fp.exists():
        continue
    parts.append(f"\n\n---\n\n## `{rel}`\n\n```{lang}\n{fp.read_text(encoding='utf-8')}\n```\n")
(OUT / "80_codigo_fuente.md").write_text("".join(parts), encoding="utf-8")
print("escrito 80_codigo_fuente.md")

# --- 3. resultados numéricos como tablas --------------------------------
def _md_kv(d: dict, indent=0) -> str:
    lines = []
    pad = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{pad}- **{k}**:")
            lines.append(_md_kv(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{pad}- **{k}**: {v}")
        else:
            lines.append(f"{pad}- **{k}**: {v}")
    return "\n".join(lines)

res = ["# Resultados numéricos (outputs/)\n",
       "Salidas de los scripts, con semilla fija (SEED=42). Reproducibles bit a bit.\n"]
for name in ["fase2_resumen.json", "fase4_resumen.json", "fase5_resumen.json"]:
    p = ROOT / "outputs/tables" / name
    if p.exists():
        res.append(f"\n\n## `{name}`\n\n")
        res.append(_md_kv(json.loads(p.read_text(encoding="utf-8"))))
for name in ["fase3_transformaciones.csv", "fase3_balance.csv", "fase3_srm.csv",
             "fase5_segmentos.csv", "mde_cost_model.csv"]:
    p = ROOT / "outputs/tables" / name
    if p.exists():
        res.append(f"\n\n## `{name}`\n\n```\n{p.read_text(encoding='utf-8')}\n```\n")
(OUT / "85_resultados_numericos.md").write_text("".join(res), encoding="utf-8")
print("escrito 85_resultados_numericos.md")

# --- 4. figuras -> un PDF ------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg

CAPTIONS = {
    "f2_01_volumen_mensual.png": "Fase 2 — Volumen mensual de pedidos; ventana estable 2017-01/2018-08.",
    "f2_02_distribucion_aov.png": "Fase 2 — Distribución del AOV: bruto (skew 9,8) vs log (casi normal).",
    "f2_03_guardrails.png": "Fase 2 — Guardrails: review_score y pedidos por cliente.",
    "f3_01_balance.png": "Fase 3 — Balance de covariables tras la asignación (todas |SMD| ≤ 0,02).",
    "f4_01_tcl_normalidad.png": "Fase 4 — Los datos no son normales; la media sí (TCL) -> Welch válido.",
    "f4_02_aa_pvalores.png": "Fase 4 — A/A: p-valores uniformes, 5% de falsos positivos.",
    "f4_03_ab_efecto.png": "Fase 4 — A/B: efecto +5,7%/+6,1%; IC sobre el MDE (+3%) y sobre el ATE real (+5%).",
    "f4_04_power_vs_n.png": "Fase 4 — La dilución del efecto apenas penaliza la potencia.",
    "f5_01_forest_segmentos.png": "Fase 5 — Efecto por segmento: homogéneo, sin interacción tras BH.",
    "f_mde_breakeven.png": "Fase 4 — MDE de relevancia derivado de costes: cae con el volumen de pedidos.",
}
figdir = ROOT / "outputs/figures"
pdf_path = OUT / "95_figuras.pdf"
with PdfPages(pdf_path) as pdf:
    for fname, cap in CAPTIONS.items():
        fp = figdir / fname
        if not fp.exists():
            continue
        img = mpimg.imread(fp)
        h, w = img.shape[:2]
        fig = plt.figure(figsize=(8.27, 8.27 * h / w + 0.9))
        ax = fig.add_axes([0.02, 0.02, 0.96, 0.9])
        ax.imshow(img); ax.axis("off")
        fig.text(0.5, 0.965, cap, ha="center", va="top", fontsize=9, wrap=True)
        pdf.savefig(fig, dpi=150)
        plt.close(fig)
print("escrito 95_figuras.pdf")

# limpiar la carpeta de imágenes que crea nbconvert (referencias rotas en NotebookLM)
imgdir = OUT / "90_notebook_ejecutado_files"
if imgdir.exists():
    shutil.rmtree(imgdir)

n_md = len(list(OUT.glob("*.md")))
print(f"\nListo. Sube a NotebookLM el CONTENIDO de la carpeta notebooklm/ ({n_md} .md + 1 .pdf).")
