# Task 7: Demand Forecasting

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 23 November 2026 (data to the 23 Nov snapshot; rerun `python src/forecast.py` after new snapshots)

## 1. Summary

`src/forecast.py` forecasts weekly new roles for OpenAI, Anthropic, Databricks and NVIDIA over a **shared 8-week horizon**, with the same seven candidate models and the same rolling-origin backtest for every company. The target is the survivorship-adjusted weekly series from Task 5 (`new_roles_adjusted`). The model is chosen by the one-standard-error rule and the intervals are empirical, from backtest errors. Walkthrough with charts: `notebooks/07_forecasting.ipynb`.

| Company | Chosen model | Relative MAE (vs naive) | Beats naive? | Forecast, new roles per week (step 1 to 8) |
|---|---|---|---|---|
| OpenAI | 4-week moving average | 0.741 | yes | 95.8 (flat) |
| Anthropic | Naive (last value) | 1.000 | **no, nothing did** | 40.5 (flat) |
| Databricks | 4-week moving average | 0.846 | yes | 54.4 (flat) |
| NVIDIA | Damped Holt | 0.837 | yes (11 origins) | 159.1 to 186.4 |

Three of the four winners are flat forecasts. The honest summary is a level for each company with wide uncertainty, not a trend call. NVIDIA is the exception and the least reliable (section 5).

**Update, 23 November 2026 (review fixes).** The first version chose models with a margin rule (relative MAE below 0.95 to beat naive) that I set after seeing the first results. It is replaced by the standard one-standard-error rule. Two picks changed: Databricks from damped Holt to the 4-week moving average, and NVIDIA from Prophet to damped Holt. OpenAI (moving average) and Anthropic (naive) are unchanged. The model-based intervals are replaced by empirical ones, because the model-based intervals for NVIDIA covered only 38% at the 80% level and 52% at the 95% level (40% and 63% for the Prophet pick it replaced).

## 2. Method

| Decision | Choice | Why |
|---|---|---|
| Target | `new_roles_adjusted` (weekly, unique roles, survivorship-corrected) | The raw series ramps up by survivorship alone, so forecasting it would extrapolate the bias (section 3) |
| Horizon | 8 weeks for all four, counted from each company's last complete week | 26 weekly points cannot support the brief's 3 to 12 months: a 12-month horizon is twice the whole history, and only 4 to 5 backtest origins have a full 8-week outcome. Eight weeks is the longest horizon I can test at all |
| Models | Naive, 4-week moving average, simple exponential smoothing, drift, damped Holt, ARIMA (p, q up to 2, d up to 1, lowest AIC), Prophet (default settings, seasonality off), in this fixed order of simplicity | Small, standard, and identical for every company. Prophet installed cleanly, so it is included |
| Excluded | Seasonal models, deep learning | Under a year of data gives no seasonality; deep learning would overfit 26 points |
| Backtest | Rolling origin, expanding window, first origin after 14 weeks, up to 8 weeks ahead from each origin | Mimics real use; one rule for every company |
| Metrics | MAE pooled over origins and steps. `rel_mae` = model backtest MAE / naive backtest MAE on the same origins and steps | Naive is 1.0, so a value below 1.0 beats naive, and results compare across companies of different size. It is relative MAE, not the classical MASE, which scales by in-sample naive errors |
| Choice rule | **One-standard-error rule.** For each model take its mean absolute error at each origin (over the steps forecast from that origin), then the mean across origins and its standard error. Find the best model, and choose the simplest model whose mean is within one SE of the best | This is the standard one-SE convention for choosing among models with noisy error estimates (Breiman et al. 1984; Hastie, Tibshirani and Friedman, *The Elements of Statistical Learning*). It prefers the simpler model when the data cannot separate it from the best. It replaced a 5% margin rule I had set after the first run |
| Intervals | Empirical: half-width at each step is the conformal-style quantile (rank ceil((n+1) x level)) of the chosen model's absolute backtest errors at that step, so the interval is symmetric around the forecast. A step with fewer than 20 errors pools neighbouring steps (window widened one step each side) until it has 20. Clipped at 0 | Model-based Gaussian intervals were badly calibrated (section 3). Empirical intervals need no distribution and are checked by leave-one-origin-out |
| Sensitivity | Unique-roles target; chosen model refit on August onwards | Checks the survivorship adjustment and the pre-August floors (correction capped at 3x) |
| Cross-check | Forecast for the next 2 weeks vs snapshot `opened_per_week` | An independent, unbiased signal. NVIDIA flagged provisional (one interval) |

NVIDIA's snapshots lag the others (latest 16 Nov, the rest 23 Nov), so its last complete week is 9 Nov and its forecast starts a week earlier (16 Nov). The horizon is 8 steps for everyone.

## 3. Validation

**Backtest relative MAE, adjusted target** (below 1.0 beats naive; bold = chosen):

| Model | OpenAI | Anthropic | Databricks | NVIDIA |
|---|---|---|---|---|
| Naive | 1.000 | **1.000** | 1.000 | 1.000 |
| 4-week moving average | **0.741** | 1.113 | **0.846** | 0.905 |
| Simple exponential smoothing | 0.773 | 1.000 | 0.969 | 0.939 |
| Drift | 1.239 | 1.731 | 1.193 | 1.006 |
| Damped Holt | 1.551 | 1.481 | 0.845 | **0.837** |
| ARIMA (AIC grid) | 0.983 | 2.492 | 0.897 | 0.891 |
| Prophet | 0.939 | 2.515 | 0.866 | 0.804 |
| Origins / forecasts | 12 / 68 | 12 / 68 | 12 / 68 | 11 / 60 |

`rel_mae` is the pooled ratio; the one-SE rule uses the mean of per-origin errors, which weights each origin equally, so its ranking can differ slightly.

**One-SE selection** (mean absolute error per origin, roles per week, with its SE):

| Company | Best model | Best mean (SE) | Threshold (best + 1 SE) | Chosen (simplest inside) | Chosen mean (SE) | Naive mean (SE) |
|---|---|---|---|---|---|---|
| OpenAI | Prophet | 17.57 (3.10) | 20.67 | 4-week moving average | 18.91 (1.93) | 20.87 (3.44) |
| Anthropic | Naive | 19.20 (2.53) | 21.72 | Naive | 19.20 (2.53) | 19.20 (2.53) |
| Databricks | 4-week moving average | 12.66 (1.01) | 13.67 | 4-week moving average | 12.66 (1.01) | 14.57 (1.38) |
| NVIDIA | Prophet | 52.63 (8.65) | 61.28 | Damped Holt | 55.88 (9.84) | 76.60 (12.80) |

**Which picks changed** from the margin rule: Databricks (damped Holt to moving average) and NVIDIA (Prophet to damped Holt). OpenAI and Anthropic did not change. For OpenAI naive is only just outside the band (20.87 against 20.67), so the choice over naive is marginal. Prophet has the lowest mean error for OpenAI and NVIDIA but is not simplest inside the band, so it is not chosen.

**Interval coverage** (share of backtest actuals inside the chosen model's intervals; empirical coverage is leave-one-origin-out, each origin tested against intervals built from the other origins' errors):

| Company (chosen model) | 80% model-based | 80% empirical | 95% model-based | 95% empirical |
|---|---|---|---|---|
| OpenAI (4-week average) | 83.8% | 80.9% | 98.5% | 97.1% |
| Anthropic (naive) | 100% | 79.4% | 100% | 94.1% |
| Databricks (4-week average) | 69.1% | 82.4% | 94.1% | 97.1% |
| NVIDIA (damped Holt) | 38.3% | 81.7% | 51.7% | 96.7% |

Before the review the coverage of the picks then in use (model-based) was OpenAI 83.8% and 98.5%, Anthropic 100% and 100%, Databricks 82.4% and 98.5% (damped Holt), NVIDIA 40.0% and 63.3% (Prophet). The empirical intervals are close to nominal for all four. The price is width: NVIDIA's backtest errors are large (the week of 2 Nov), so its 95% interval runs from 0 to about 410 around a forecast of about 160. The check reuses errors from later origins, so it is leave-one-out, not a pure out-of-time test. Every interval is built from at least 21 errors.

**Survivorship check.** On the unadjusted `new_roles_unique` series Prophet or ARIMA beats naive for every company (best relative MAE 0.78 to 0.79, against 0.74 to 1.00 for the chosen models on the adjusted target). On the adjusted series trend models help clearly only for Databricks and NVIDIA. The unadjusted series carries the survivorship ramp, which trend models extrapolate; this is the reason the target is the adjusted series.

**Sensitivity of the forecast** (mean over the 8 weeks, against the base forecast):

| Company | Base | Unique-roles target (same model) | Refit from August (same model) |
|---|---|---|---|
| OpenAI | 95.8 | 81.5 (-14.9%) | 95.8 (0.0%) |
| Anthropic | 40.5 | 39.0 (-3.7%) | 40.5 (0.0%) |
| Databricks | 54.4 | 47.5 (-12.8%) | 54.4 (0.0%) |
| NVIDIA | 173.0 | 227.3 (+30.7%) | 280.9 (+61.2%) |

The moving average and naive use only the latest weeks, so refitting from August cannot change them. The unique-roles levels are lower for the first three mostly because the adjustment itself raises the series. NVIDIA is different: its trend model gives a higher forecast on the unique series (probably extrapolating the survivorship ramp) and on a shorter window, so its trend is not stable.

**Cross-check against snapshot inflow** (forecast for the next 2 weeks vs `opened_per_week`, 4 to 23 Nov; NVIDIA 4 to 16 Nov):

| Company | Forecast, next 2 weeks | Snapshot opened per week | Ratio |
|---|---|---|---|
| OpenAI | 95.8 | 82.5 | 1.16 |
| Anthropic | 40.5 | 44.6 | 0.91 |
| Databricks | 54.4 | 50.1 | 1.09 |
| NVIDIA (provisional) | 161.2 | 145.8 | 1.11 |

All four are within 16% of the flows. The forecast counts unique roles and the flows count postings, so a ratio near 1 is a loose agreement, not a test.

**Sanity checks (run and fail loudly on every run of `forecast.py`):** same 8-step horizon for all four; same seven models for all four; no negative forecasts or bounds; lo95 <= lo80 <= forecast <= hi80 <= hi95; exactly one chosen model per company and target; weekly series contiguous; every interval built from at least 20 backtest errors; every model produced a forecast at every origin; and a leakage test that replaces all data after an origin with different values and confirms every model's forecast at that origin is unchanged (all models, all companies).

## 4. Outputs (`data/processed/`, all committed: no description text)

| File | What | Used in |
|---|---|---|
| `forecasts.csv` | Per company and step (1 to 8): `week_start`, `model`, `forecast`, empirical `lo80`, `hi80`, `lo95`, `hi95`, `n_errors` (errors behind the interval) | Tasks 8, 9, 10 |
| `backtest_metrics.csv` | Company x target x model: `mae`, `rel_mae` (relative MAE vs naive), `origin_mae`, `origin_mae_se`, `one_se_threshold`, `within_1se_of_best`, `best_model`, `chosen`, coverage at 80% and 95% (`_model` and `_empirical`), `n_origins`, `n_forecasts` | Task 9 |
| `forecast_sensitivity.csv` | Company x scenario (`base`, `unique_target`, `from_august`) x week: `forecast`, `base_forecast`, `diff_pct`, `n_weeks_fitted` | Task 9 |
| `forecast_crosscheck.csv` | Forecast for the next 2 weeks vs `opened_per_week`, `ratio`, `flows_provisional` | Task 9 |

`forecasts.csv` uses the shared structure of Task 5 (`company_name` + `week_start` + metrics), so it joins directly to `weekly_postings.csv`. The unit is weekly unique new roles, survivorship-adjusted. Forecasts do not refresh with the snapshot schedule; rerun `python src/forecast.py` after `trends.py`.

## 5. Key findings

**OpenAI (main company).**
- **Chosen model and why:** the 4-week moving average. Prophet has the lowest mean error but the moving average is inside one SE of it and is simpler, so the one-SE rule picks it. It beats naive by 26% on relative MAE (0.741, MAE 17.2 roles a week), the largest gain of the four. By the one-SE measure naive sits only just outside the band, so the evidence against naive is thinner than the pooled number suggests.
- **Forecast:** a flat 95.8 new roles a week for 23 Nov to 11 Jan. The empirical 80% interval is about 62 to 129 and the 95% interval about 46 to 146 (it varies a little by step, because few origins reach step 8). This is a level, not a trend: the model has no view on direction.
- **Agreement:** the forecast is 1.16 times the 82.5 roles a week OpenAI opened in the snapshots. OpenAI is the only company whose open stock grew (Task 5), and the forecast does not contradict that, but it cannot confirm acceleration either.
- **Sensitivity:** unchanged when refitted from August; 15% lower on the unique-roles target, which is the adjustment itself.

**Anthropic.** Naive is the best model, and nothing beat it (the 4-week average scores 1.113, SES 1.000, ARIMA and Prophet about 2.5), so the forecast is the last value, 40.5 a week. The empirical 80% interval is about 12 to 69 at step 1 and 0 to 81 by step 8; the 95% interval reaches 0 to 91. Coverage is 79% and 94%, close to nominal, so the old model-based intervals (100%) were far too wide. It is the least predictable series and the one where Task 5 already marked adjusted growth as low confidence. Cross-check ratio 0.91.

**Databricks.** The 4-week moving average is both the best by mean error (12.66) and the simplest model inside the band (damped Holt scores almost the same, 13.05). The forecast is a flat 54.4 a week (80% interval about 34 to 75). The first version picked damped Holt and a slowly rising forecast (57 to 60); the one-SE rule removes that trend. Refitting from August changes nothing for a moving average. Cross-check ratio 1.09.

**NVIDIA (provisional).**
- **Chosen model and why:** damped Holt (relative MAE 0.837), the simplest model inside one SE of Prophet, which has the lowest mean error. The first version chose Prophet.
- **Forecast:** rising from 159.1 (week of 16 Nov) to 186.4 (4 Jan). The trend leans on the large week of 2 Nov (274 unique roles, flagged as a spike in Task 5), and the snapshot flows do not show growth: NVIDIA's open stock fell 2.4% over its one 12-day interval.
- **Reliability:** the empirical intervals are close to nominal in the backtest (82% and 97%) but very wide: the 80% interval is about 118 to 200 at step 1 and reaches 0 at steps 7 and 8, and the 95% interval runs from 0 to about 410. The forecast itself is unstable: refit from August the damped Holt forecast is 61% higher, and on the unique-roles series 31% higher. The cross-check (1.11) uses provisional flows. Treat the NVIDIA forecast as a wide range, not a number.

**Across companies.** The forecast ranking by weekly new roles is NVIDIA (about 173 on average), OpenAI (96), Databricks (54), Anthropic (41). Only NVIDIA has a forecast that moves, and it is the one the checks trust least. On the unadjusted series trend models win for all four companies, which reflects the survivorship ramp rather than hiring.

## 6. Limitations

- **Short history.** 26 weekly points (NVIDIA 25), 11 to 12 backtest origins, only 4 to 5 with a full 8-week outcome. Model choice rests on small differences; the one-SE rule is the guard against over-reading them, and several models are inside the band for every company.
- **The target is an estimate.** `new_roles_adjusted` divides by a survival curve estimated from 19 days of closures, capped at 3x. Weeks before about August are floors, and adjusted growth moved about 30 points between two snapshots (Task 5). Forecasts will move when the series is refreshed.
- **Flat forecasts say nothing about direction.** The OpenAI, Anthropic and Databricks forecasts are levels. They answer "how many roles a week at the recent pace", not "will hiring grow".
- **Empirical intervals are approximate.** With 11 to 12 origins each interval rests on 21 to 33 pooled errors, so the 95% bound is close to the largest observed error. Intervals do not widen smoothly with the horizon because the data cannot resolve how error grows over 8 weeks. Coverage was checked leave-one-origin-out, which reuses errors from later origins.
- **NVIDIA is the weakest forecast.** Its snapshots lag (latest 16 Nov), its flows are one interval, its series holds the 2 Nov spike, its backtest errors are large (so its intervals are very wide) and its damped Holt forecast moves a lot with the data window (+61% refit from August). Treat it as provisional.
- **Anthropic has no model that beats naive.** The forecast is the last value, and the series is too jumpy for a tight interval (80%: 0 to 81 by week 8).
- **Selection among seven models on the same backtest** still gives the chosen model an optimistic error. The one-SE rule limits this but does not remove it.
- **The horizon spans the year end.** The data holds no December or January, so how postings behave over the holidays is unknown, and the forecast ignores it.
- **No seasonality, no external drivers.** Hiring is not modelled against product launches, funding or the economy.
