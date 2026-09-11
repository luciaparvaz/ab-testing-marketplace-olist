# Executive summary — A/B test of the product page redesign

**Project:** product experimentation in a marketplace (public Brazilian E-Commerce by Olist
dataset) · **Methodology:** CRISP-DM · **Date:** 2026

---

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
| **Relevance threshold** | The AOV must rise by **at least +3%** for the change to offset its development and maintenance cost (a figure obtained from a break-even model; valid for the order volume of a medium-large marketplace) |
| **Rule** | **Launch** only if the improvement is statistically solid **and** its confidence interval is entirely above +3% **and** no guardrail degrades |

## The result

| | |
|---|---|
| **Effect on the AOV** | **+5.7%** (95% confidence interval: **+4.0% to +7.3%**); estimate between +5.7% and +6.1% depending on the treatment of extreme values |
| **Statistical strength** | Very high (p ≈ 0.00000000003); confirmed with five alternative methods and with 500 repetitions of the experiment |
| **Guardrails** | **None degrades** (satisfaction, cancellations, shipping, and basket size all hold steady) |
| **Does it work better in any segment?** | No: the relative effect is **homogeneous** across payment type, region, category, basket size, and quarter |
| **Estimated economic impact** | **+R$ 456,000 per year** in merchandise value (interval: +R$ 322,000 to +R$ 591,000); ≈ **+R$ 68,000 per year** in commission revenue |

## The decision

# 🟢 LAUNCH

The AOV improvement is statistically solid, **materially relevant** (the entire confidence
interval clears the +3% threshold set by the business), and **has no cost** on any control
metric. Rolling out the redesign to 100% of traffic is recommended, monitoring the AOV and the
guardrails over the following four weeks.

## What to watch after launch

- The real AOV at 4 weeks against the expected **+3% minimum**.
- The return and complaint rate (not measurable in this dataset; measurable in production).
- That the effect does not dilute due to novelty: review again at 90 days.

---

## Methodological note (essential)

> This is a **portfolio project** built on a public dataset that **does not contain a real
> experiment**. The split into control/treatment groups and the redesign's effect are
> **simulated and declared** (mean effect +5%, concentrated in the 20% of users who respond).
> Therefore, **this report does not describe a real finding about Olist**: it demonstrates that
> the **design, analysis, and decision process** is correct —it controls false positives
> (validated over 2,000 random partitions), recovers an effect of known size without bias, and
> distinguishes statistical significance from business relevance—. This is exactly the work a
> product experimentation team does.

*Full CRISP-DM per-phase documentation and statistical audits are in the repository.*
