# 🎯 PROJECT MANDATE & ECONOMIC EVALUATION FRAMEWORK

> **Core Philosophy**: The ultimate objective of this system is **Sustainable Net Profitability (الربح الصافي المستدام)** with a mathematically proven quantitative edge. We do not build complexity for the sake of complexity, nor do we retain "smart" features that do not generate measurable economic value.

---

## 📐 1. Economic Evaluation Metrics (معايير التقييم الاقتصادي)

Every component, filter, regime classifier, or risk rule in the Quantitative Decision System (QDS) must be validated against the following strict economic metrics:

1. **Net PnL ($\text{Net PnL}$)**: Total net profit in USD after deducting all commissions, slippage, and spread costs.
2. **Expectancy ($\text{Expectancy}$)**:
   $$\text{Expectancy} = (\text{Win Rate} \times \text{Average Win USD}) - (\text{Loss Rate} \times \text{Average Loss USD})$$
3. **Profit Factor ($\text{Profit Factor}$)**:
   $$\text{Profit Factor} = \frac{\sum \text{Gross Profits}}{\sum \text{Gross Losses}} \quad (\text{Target} > 1.50)$$
4. **Max Drawdown ($\text{Max DD}$)**: Mitigation of maximum peak-to-trough decline without disproportionately sacrificing total net profit.
5. **Out-of-Sample (OOS) Robustness**: Performance stability across unseen data and varying market conditions.

---

## 🔄 2. Strict Project Pipeline (مسار التطوير المعتمد)

$$\text{Build} \longrightarrow \text{Observe} \longrightarrow \text{Measure} \longrightarrow \text{Validate} \longrightarrow \text{Optimize for Profit}$$

* **STRICT RULE**: NO premature parameter optimization, NO adding features in loops, and NO threshold tuning until sufficient statistical sample sizes are gathered across diverse market regimes.

---

## ✂️ 3. Component Elimination & Ablation Protocol (معيار حذف المكونات)

* No module or feature is retained solely because it sounds logical, advanced, or sophisticated.
* If **Ablation Testing** (`Legacy`, `Legacy + Regime`, `Legacy + Risk`, `Legacy + Gemini`, `Full QDS`) demonstrates that a module does NOT increase Net PnL, Expectancy, or Profit Factor, or if it needlessly restricts profitable trades:
  👉 **It MUST be pruned or disabled.**

---

## 📊 4. Operational & Observability Guidelines (إرشادات التشغيل والتتبع)

1. **Legacy Engine**: Runs 100% untouched as the baseline benchmark ($1000 initial balance per symbol across 5 pairs).
2. **Shadow QDS Engine**: Operates in sidecar mode, evaluating decisions without altering paper trading state or balances.
3. **Trade Memory & Horizon Tracking**: Record complete context (Market Regime, Technical Score, Risk, Gemini Status) along with post-decision forward price horizons (4h, 12h, 24h, 48h) and excursion analytics (MFE, MAE) for all decisions (`BUY` and `WAIT`).
