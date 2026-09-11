# Draft — LinkedIn post

*(personal tone, in English for an international Berlin audience. ~230 words. Add 2-3 images:
segment forest plot, power curve, and the balance love-plot.)*

---

I just finished a project on **A/B testing in a marketplace**, and I'm left with a lesson I
wasn't expecting.

**The setup:** I simulated the test of a product-page redesign (cross-sell + free-shipping
progress bar) on public e-commerce data, following CRISP-DM end to end: hypothesis, primary
metric, guardrails, power calculation, and a decision rule written **before** looking at the data.

**The interesting part was the segment analysis.** The effect I injected was homogeneous: the
same % lift for everyone. Even so, if I measured the impact in **absolute value (R$)** and sliced
the data by variables correlated with order size, I "found" segments where the effect was clearly
larger... and those false findings **survived even the Bonferroni correction**.

The cause: a multiplicative effect automatically generates more euros of lift in large baskets.
It wasn't real heterogeneity, it was an artifact of measuring the wrong magnitude.

**The takeaway:** correcting for multiple comparisons doesn't save you if the *estimand* is
wrongly posed. You have to test the correct business question (does the **%** change?), not the
one that first comes out of the `groupby`.

All the code, the per-phase documentation, and four statistical audits are in the repo 👇

#DataScience #ABTesting #Experimentation #ProductAnalytics #CRISPDM

---

## Short variant (for X / Bluesky, ~110 words)

New project: A/B testing an e-commerce redesign, full CRISP-DM.

What surprised me most: with an effect that was **homogeneous** by construction, measuring the
impact in absolute R$ (instead of %) and slicing by variables tied to basket size produced false
"winning segments" that **survived Bonferroni**.

A multiplicative effect gives more euros of lift on large orders → looks heterogeneous, but isn't.

Correcting for multiplicity doesn't fix a badly chosen estimand. Repo with code + audits 👇
