# 🎯 CryptoPaperBot — Project Mandate & Quantitative Evaluation Framework

> **الهدف الأسمى والوحيد للمشروع:**  
> **تحقيق ربح صافٍ مستدام (Sustainable Net PnL) ذي ميزة كمية مثبتة (Quantifiable Edge)، وليس بناء نظام أكثر تعقيداً أو إضافة تقنيات زوائد.**

---

## 📐 1. خوارزمية التقييم الاقتصادي الصارمة (KPI Evaluation Criteria)

أي مكون برمجي، استراتيجية، أو وحدة تحليل جديدة لن تُعتمد إلا إذا أثبتت بالبيانات الفعلية قدرتها على تحسين المعايير المالية التالية:

1. **Net PnL (الربح الصافي النهائي):** زيادة مجموع الأرباح بعد احتساب الرسوم والانزلاق.
2. **Expectancy (العائد المتوقع لكل صفقة):**
   $$E = (\text{Win Rate} \times \text{Average Win}) - (\text{Loss Rate} \times \text{Average Loss})$$
3. **Profit Factor (معامل الربحية):**
   $$\text{Profit Factor} = \frac{\text{Gross Profit}}{\text{Gross Loss}} > 1.5$$
4. **Max Drawdown Reduction:** تقليل أقصى تراجع بدون التضحية بنسبة أكبر من الأرباح.
5. **Out-of-Sample Robustness:** الحفاظ على الأداء المربح عبر حالات السوق المختلفة (`TRENDING_UP`, `TRENDING_DOWN`, `SIDEWAYS`, `HIGH_VOLATILITY`).

---

## ✂️ 2. معيار الاقتطاع الصارم (Ablation Rule)

* **لا قيمة منطقية أو تقنية لأي مكوّن لم يُثبت ربحيته بالبيانات.**
* إذا أظهرت نتائج المراقبة والـ Ablation Testing أن مكوّناً معيناً (مثل فلاتر الذكاء الاصطناعي، أو محرك النظام، أو فلاتر المخاطرة) يقلل الأرباح الصافية أو يُفوت صفقات ذات Expectancy إيجابي، **يتم استبعاده وحذفه فوراً** مهما كان متقدماً تقنياً.

---

## 🔄 3. دورة التطوير المعتمدة (Development Lifecycle)

$$\text{Build} \longrightarrow \text{Observe} \longrightarrow \text{Measure} \longrightarrow \text{Validate} \longrightarrow \text{Optimize for Profit}$$

* 🚫 **ممنوع:** $\text{Build} \rightarrow \text{Add Features} \rightarrow \text{Add Features} \rightarrow \text{Add Features}$
* ✅ **المعتمد:** الصبر التام على جمع بيانات المراقبة والقياس عبر وضع الظل (`Shadow Mode`) بدون أي تعديل مبكر في المعايير أو الاستراتيجية.

---

## 📊 4. التتبع المستقبلي وتصنيف الأداء (Performance Segmentation)

يتم الاحتفاظ بجميع بيانات `trade_memory.json` لتحليل الأداء حسب:
1. **Market Regime:** معرفة أي ظروف سوق تحقق أعلى Expectancy.
2. **Asset:** تحديد أفضل الأصول استجابةً للشبكة.
3. **Signal Type & Timeframe:** تقييم جودة الإشارات المطبقة على شمعة الـ 4H.
