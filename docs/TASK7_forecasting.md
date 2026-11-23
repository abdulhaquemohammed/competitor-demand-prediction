# Task 7: Demand Forecasting

**Project:** Competitor Demand Prediction Using Job Postings (CadetX)
**Author:** Abdul-Haque Mohammed (individual track)
**Date:** 23 November 2026 (data to the 23 Nov snapshot; rerun `python src/forecast.py` after new snapshots)

## 1. Summary

`src/forecast.py` forecasts weekly new roles for OpenAI, Anthropic, Databricks and NVIDIA over a **shared 8-week horizon**, with the same seven candidate models and the same rolling-origin backtest for every company. The target is the survivorship-adjusted weekly series from Task 5 (`new_roles_adjusted`). Walkthrough with charts: `notebooks/07_forecasting.ipynb`.

| Company | Chosen model | Backtest MASE (vs naive) | Beats naive? | Forecast, new roles per week (step 1 to 8) |
|---|---|---|---|---|
| OpenAI | 4-week moving average | 0.741 | yes | 95.8 (flat) |
| Anthropic | Naive (last value) | 1.000 | **no, nothing did** | 40.5 (flat) |
| Databricks | Damped Holt | 0.845 | yes | 56.9 to 59.5 |
| NVIDIA | Prophet (no seasonality) | 0.804 | yes (11 origins) | 166.8 to 206.0 |

Two of the four winners are flat forecasts. The honest summary is a level for each company with wide uncertainty, not a trend call.

## 2. Method

| Decision | Choice | Why |
|---|---|---|
| Target | `new_roles_adjusted` (weekly, unique roles, survivorship-corrected) | The raw series ramps up by survivorship alone, so forecasting it would extrapolate the bias (section 3) |
| Horizon | 8 weeks for all four, counted from each company's last complete week | 26 weekly points cannot support the brief's 3 to 12 months: a 12-month horizon is twice the whole history, and only 4 to 5 backtest origins have a full 8-week outcome. Eight weeks is the longest horizon I can test at all |
| Models | Naive, 4-week moving average, drift, simple exponential smoothing, damped Holt, ARIMA (p, q up to 2, d up to 1, lowest AIC), Prophet (default settings, seasonality off) | Small, standard, and identical for every company. Prophet installed cleanly, so it is included |
| Excluded | Seasonal models, deep learning | Under a year of data gives no seasonality; deep learning would overfit 26 points |
| Backtest | Rolling origin, expanding window, first origin after 14 weeks, up to 8 weeks ahead from each origin | Mimics real use; one rule for every company |
| Metrics | MAE pooled over origins and steps. MASE = model MAE / naive MAE on the same origins and steps | Naive is 1.0, so MASE below 1.0 beats naive, and results compare across companies of different size |
| Choice rule | Lowest MASE. A model must score below 0.95 to be chosen over naive; otherwise naive is used | 12 origins cannot separate smaller differences, and a model that only matches naive should not be presented as better. The margin was fixed after I saw that Anthropic's best "winner" scored 1.00 |
| Intervals | Gaussian around each model's forecast, from its own standard error, 80% and 95%, clipped at 0 | One method for all models; coverage is tested in the backtest |
| Sensitivity | Unique-roles target; chosen model refit on August onwards | Checks the survivorship adjustment and the pre-August floors (correction capped at 3x) |
| Cross-check | Forecast for the next 2 weeks vs snapshot `opened_per_week` | An independent, unbiased signal. NVIDIA flagged provisional (one interval) |

NVIDIA's snapshots lag the others (latest 16 Nov, the rest 23 Nov), so its last complete week is 9 Nov and its forecast starts a week earlier (16 Nov). The horizon is 8 steps for everyone.

## 3. Validation

**Backtest MASE, adjusted target** (lower is better; naive is 1.0; bold = chosen):

| Model | OpenAI | Anthropic | Databricks | NVIDIA |
|---|---|---|---|---|
| Naive | 1.000 | **1.000** | 1.000 | 1.000 |
| 4-week moving average | **0.741** | 1.113 | 0.846 | 0.905 |
| Drift | 1.239 | 1.731 | 1.193 | 1.006 |
| Simple exponential smoothing | 0.773 | 1.000 | 0.969 | 0.939 |
| Damped Holt | 1.551 | 1.481 | **0.845** | 0.837 |
| ARIMA (AIC grid) | 0.983 | 2.492 | 0.897 | 0.891 |
| Prophet | 0.939 | 2.515 | 0.866 | **0.804** |
| Chosen MAE (roles per week) | 17.19 | 20.25 | 11.82 | 48.72 |
| Origins / forecasts | 12 / 68 | 12 / 68 | 12 / 68 | 11 / 60 |

The Databricks result is a tie (damped Holt 0.845, moving average 0.846). The winner is picked from seven models on the same 11 to 12 origins, so its MASE is somewhat optimistic.

**Interval coverage** (share of backtest actuals inside the chosen model's intervals):

| Company | 80% interval | 95% interval | Verdict |
|---|---|---|---|
| OpenAI | 83.8% | 98.5% | about right, slightly wide at 95% |
| Anthropic | 100% | 100% | far too wide |
| Databricks | 82.4% | 98.5% | about right, slightly wide at 95% |
| NVIDIA | 40.0% | 63.3% | **too narrow**: read as optimistic |

**Survivorship check.** On the unadjusted `new_roles_unique` series Prophet or ARIMA beats naive for every company (best MASE 0.78 to 0.79, against 0.74 to 1.00 on the adjusted target). On the adjusted series trend models help clearly only for Databricks and NVIDIA. The unadjusted series carries the survivorship ramp, which trend models extrapolate; this is the reason the target is the adjusted series.

**Sensitivity of the forecast** (mean over the 8 weeks, against the base forecast):

| Company | Base | Unique-roles target (same model) | Refit from August (same model) |
|---|---|---|---|
| OpenAI | 95.8 | 81.5 (-14.9%) | 95.8 (0.0%) |
| Anthropic | 40.5 | 39.0 (-3.7%) | 40.5 (0.0%) |
| Databricks | 58.3 | 56.2 (-3.5%) | 54.6 (-6.3%) |
| NVIDIA | 186.4 | 151.0 (-19.1%) | 209.0 (+12.0%) |

The unique-roles levels are lower mostly because the adjustment itself raises the series, not because of a different view of the trend. The moving average and naive use only the latest weeks, so refitting from August cannot change them. Databricks moves down about 6%. NVIDIA moves up about 12% with a steeper trend.

**Cross-check against snapshot inflow** (forecast for the next 2 weeks vs `opened_per_week`, 4 to 23 Nov; NVIDIA 4 to 16 Nov):

| Company | Forecast, next 2 weeks | Snapshot opened per week | Ratio |
|---|---|---|---|
| OpenAI | 95.8 | 82.5 | 1.16 |
| Anthropic | 40.5 | 44.6 | 0.91 |
| Databricks | 57.1 | 50.1 | 1.14 |
| NVIDIA (provisional) | 169.6 | 145.8 | 1.16 |

All four are within 16% of the flows. The forecast counts unique roles and the flows count postings, so a ratio near 1 is a loose agreement, not a test.

**Sanity checks (run and fail loudly on every run of `forecast.py`):** same 8-step horizon for all four; same seven models for all four; no negative forecasts or bounds; lo95 <= lo80 <= forecast <= hi80 <= hi95; exactly one chosen model per company and target; weekly series contiguous; every model produced a forecast at every origin; and a leakage test that replaces all data after an origin with different values and confirms every model's forecast at that origin is unchanged (all models, all companies).

## 4. Outputs (`data/processed/`, all committed: no description text)

| File | What | Used in |
|---|---|---|
| `forecasts.csv` | Per company and step (1 to 8): `week_start`, `model`, `forecast`, `lo80`, `hi80`, `lo95`, `hi95` | Tasks 8, 9, 10 |
| `backtest_metrics.csv` | Company x target x model: `mae`, `mase`, `coverage80`, `coverage95`, `n_origins`, `n_forecasts`, `chosen`, `beats_naive` (MASE below 0.95) | Task 9 |
| `forecast_sensitivity.csv` | Company x scenario (`base`, `unique_target`, `from_august`) x week: `forecast`, `base_forecast`, `diff_pct`, `n_weeks_fitted` | Task 9 |
| `forecast_crosscheck.csv` | Forecast for the next 2 weeks vs `opened_per_week`, `ratio`, `flows_provisional` | Task 9 |

`forecasts.csv` uses the shared structure of Task 5 (`company_name` + `week_start` + metrics), so it joins directly to `weekly_postings.csv`. The unit is weekly unique new roles, survivorship-adjusted. Forecasts do not refresh with the snapshot schedule; rerun `python src/forecast.py` after `trends.py`.

## 5. Key findings

**OpenAI (main company).**
- **Chosen model and why:** the 4-week moving average. Its backtest error is 26% below naive (MASE 0.741, MAE 17.2 roles a week), the best margin of the four companies. Simple exponential smoothing is close (0.773); Prophet and ARIMA barely beat naive (0.939 and 0.983).
- **Forecast:** a flat 95.8 new roles a week for 23 Nov to 11 Jan (80% interval 67 to 124, 95% interval 52 to 139). This is a level, not a trend: the model has no view on direction.
- **Agreement:** the forecast is 1.16 times the 82.5 roles a week OpenAI opened in the snapshots. OpenAI is the only company whose open stock grew (Task 5), and the forecast does not contradict that, but it cannot confirm acceleration either.
- **Sensitivity:** unchanged when refitted from August; 15% lower on the unique-roles target, which is the adjustment itself.

**Anthropic.** Nothing beat naive: the moving average scores 1.113, simple smoothing 1.000, and ARIMA and Prophet about 2.5. The forecast is the last value, 40.5 a week. The 80% interval spans 6 to 75 at step 1 and 0 to 138 by step 8, and the backtest shows it is too wide (100% coverage). It is the least predictable series and the one where Task 5 already marked adjusted growth as low confidence. Cross-check ratio 0.91.

**Databricks.** Damped Holt (MASE 0.845) tied with the moving average (0.846). The forecast drifts from 56.9 to 59.5 a week. Refitting from August lowers it by 6.3%, so the level is modestly sensitive to the early weeks. Cross-check ratio 1.14.

**NVIDIA (provisional).**
- **Chosen model and why:** Prophet, MASE 0.804 on 11 origins, ahead of damped Holt (0.837).
- **Forecast:** rising from 166.8 (week of 16 Nov) to 206.0 (4 Jan). The trend leans on the large week of 2 Nov (274 unique roles, flagged as a spike in Task 5), and the snapshot flows do not show growth: NVIDIA's open stock fell 2.4% over its one 12-day interval.
- **Reliability:** the intervals under-cover badly (40% at 80%, 63% at 95%), the refit from August raises the forecast by 12%, and the cross-check (1.16) uses provisional flows. Treat the NVIDIA forecast as the least reliable of the four.

**Across companies.** The forecast ranking by weekly new roles is NVIDIA (about 186 on average), OpenAI (96), Databricks (58), Anthropic (41). Only NVIDIA and Databricks have a forecast that moves. On the unadjusted series trend models win for all four companies, which reflects the survivorship ramp rather than hiring.

## 6. Limitations

- **Short history.** 26 weekly points (NVIDIA 25), 11 to 12 backtest origins, only 4 to 5 with a full 8-week outcome. Model choice rests on small differences; the winner's MASE is optimistic because it was picked from seven.
- **The target is an estimate.** `new_roles_adjusted` divides by a survival curve estimated from 19 days of closures, capped at 3x. Weeks before about August are floors, and adjusted growth moved about 30 points between two snapshots (Task 5). Forecasts will move when the series is refreshed.
- **Flat forecasts say nothing about direction.** The OpenAI and Anthropic forecasts are levels. They answer "how many roles a week at the recent pace", not "will hiring grow".
- **Intervals are approximate.** They are Gaussian. They are about right for OpenAI and Databricks, too wide for Anthropic and too narrow for NVIDIA (Prophet's intervals reflect trend uncertainty only).
- **The horizon spans the year end.** The data holds no December or January, so how postings behave over the holidays is unknown, and the forecast ignores it.
- **NVIDIA.** Its snapshots lag (latest 16 Nov), its flows are one interval, and its series holds the 2 Nov spike.
- **The 5% margin is a judgement.** It was fixed after seeing that Anthropic's best non-naive model scored 1.00. Without it Anthropic's chosen model would be simple smoothing, which on its own scores no better than naive.
- **No seasonality, no external drivers.** Hiring is not modelled against product launches, funding or the economy.
