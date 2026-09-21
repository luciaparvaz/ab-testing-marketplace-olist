# Executive summary — A/B test of the product page redesign

**Project:** product experimentation in a marketplace (public Brazilian E-Commerce by Olist
dataset) · **Methodology:** CRISP-DM · **Date:** 2026

---

## Methodological note (read this first — it shapes everything else in this document)

> This is a **portfolio project** built on a public dataset that **does not contain a real
> experiment**. The split into control/treatment groups and the redesign's effect are
> **simulated and declared** (mean effect +5%, concentrated in the 20% of users who respond).
> Therefore, **this report does not describe a real finding about Olist**: it demonstrates that
> the **design, analysis, and decision process** is correct —it controls false positives
> (validated over 2,000 random partitions), recovers an effect of known size without bias, and
> distinguishes statistical significance from business relevance—. This is exactly the work a
> product experimentation team does — including the part where you revisit your own conclusions:
> a later review of this project found that the first version of this document recommended
> "LAUNCH" by mixing two incompatible business scales (see "The decision" below); it was fixed
> with code, not just by rewriting the text.

## The business question

The Product team proposes a **product page redesign** — "products often bought together"
(*cross-sell*) recommendations plus a progress bar toward free shipping. The hypothesis:
customers will add items and the **average order value (AOV) will rise**, without satisfaction or
cancellations getting worse.

**Should the change be rolled out to all users?**

## How it was decided (before looking at any data)

| | |
|---|---|
| **Success metric** | Average order value (AOV) |
| **Control metrics** ("guardrails") | Review score, cancellation rate, shipping cost, number of items per order |
| **Declared relevance threshold** | The AOV must rise by **at least +3%** for the change to offset its development and maintenance cost (a figure obtained from a break-even model) — **but that +3% is only correct for a marketplace with ≥ ~415,000 orders/year**, a fact that wasn't cross-checked against the real volume until this review (see "The decision") |
| **Rule** | **Launch** only if the improvement is statistically solid **and** its confidence interval is entirely above the relevance threshold **that matches the real volume** **and** no guardrail degrades |

## The result

| | |
|---|---|
| **Effect on the AOV** | **+5.7%** (95% confidence interval: **+4.0% to +7.3%**); estimate between +5.7% and +6.1% depending on the treatment of extreme values |
| **Statistical strength** | Very high (p ≈ 0.00000000003); confirmed with five alternative methods and with 500 repetitions of the experiment — but "significant" is not the same as "clears the launch gate": see below |
| **Guardrails** | **None degrades** (satisfaction, cancellations, shipping, and basket size all hold steady; the basket-size threshold now has a quantified magnitude, it used to gate on significance alone) |
| **Does it work better in any segment?** | No: the relative effect is **homogeneous** across payment type, region, category, basket size, and quarter |
| **Dataset volume** | ~58,700 orders/year — the **real** volume the economic impact below is computed on |
| **Estimated economic impact** | **+R$ 456,000 per year** in merchandise value (interval: +R$ 322,000 to +R$ 591,000); ≈ **+R$ 68,000 per year** in commission revenue — **against a redesign cost of ~R$ 410,000 over 2 years**: at this volume, the expected margin does not clearly cover the cost |

## The decision

# 🟡 ITERATE (not LAUNCH)

The effect is real, positive, and statistically very solid — but **it does not clear the
relevance threshold that matches this dataset's real volume**. The +3% declared during business
design is the correct break-even only for a ~7x larger marketplace (≥ ~415,000 orders/year); at
the real volume (~58,700 orders/year), the project's own cost model requires a break-even of
**+21.2%**, well above both the true effect (+5%) and the observed one (+5.7%). With the decision
rule applied correctly to the real volume, the recommendation is to **iterate** — on the design
(look for a larger effect) or on the business case (lower the development/maintenance cost, or
validate this on a higher-volume marketplace) — not to roll out to 100% of traffic yet.

*(Under the declared MDE without this volume adjustment, the decision would have been "LAUNCH" —
that is how an earlier version of this same document was published. That is the contradiction
this review fixed: the full numeric detail, with both decisions, is in `2_impacto_negocio` of
[`outputs/tables/fase5_resumen.json`](../outputs/tables/fase5_resumen.json).)*

## A second finding from this review: the power of the rule, not just of the test

Beyond the point above, re-running the full experiment 500 times (re-split + re-inject the effect)
shows that the gate "95% CI entirely above the declared MDE (+3%)" only fires in **~50% of the
re-randomizations** — even though the test rejects H0 almost every time (power ≈ 100%). This
repository's specific split (fixed seed) gave a favorable result partly because the treatment
group happened, by chance, to start with a baseline AOV ~1.2% higher than control (now measured
and declared, not just observed). Neither correction changes the experimental design itself —
what changes is which business conclusion is actually consistent with that design.

## What to watch if iterating and relaunching

- If development/maintenance cost is reduced or this is validated at a larger volume: repeat this
  same analysis with the break-even recalculated at the new scale.
- The real AOV against the break-even that matches the actual rollout volume, not the generic +3%.
- The return and complaint rate (not measurable in this dataset; measurable in production).
- That the effect does not dilute due to novelty: review again at 90 days if it is ever deployed.

---

*Full CRISP-DM per-phase documentation and statistical audits are in the repository.*
