"""
Task 7: demand forecasting.

Reads  data/processed/weekly_postings.csv, snapshot_flows.csv, velocity_summary.csv
       (Task 5; no scraping, no description text)
Writes data/processed/ (all committed):
  forecasts.csv             company_name, step, week_start, model, forecast, lo80, hi80, lo95, hi95, n_errors
  backtest_metrics.csv      company x target x model: MAE, relative MAE, per-origin error and SE, interval
                            coverage (model-based and empirical), n_origins, chosen
  forecast_sensitivity.csv  company x scenario x week: base forecast vs the unique-roles target and
                            vs a refit on August onwards
  forecast_crosscheck.csv   forecast level for the next 2 weeks vs the snapshot opened_per_week

Target: weekly new_roles_adjusted (survivorship-adjusted unique new roles). Sensitivity targets:
new_roles_unique, and the same model refitted on August onwards (weeks before about August are
floors because the survivorship correction is capped at 3x).

Horizon: 8 steps (weeks) ahead for every company, counted from that company's last complete week.
NVIDIA's snapshots lag the others, so its last complete week is one week earlier.

Candidate models, identical for every company, in order of simplicity: naive (last value), 4-week
moving average, simple exponential smoothing, drift, Holt with damped trend, ARIMA (small order grid
chosen by AIC) and Prophet (default settings, seasonality off; skipped if it is not installed). No
seasonal models and no deep learning: 26 weekly points cannot support them.

Backtest: rolling origin, expanding window, first origin after 14 weeks, each origin forecasts up
to 8 weeks ahead (fewer near the end of the data). rel_mae is the model's backtest MAE divided by
the naive forecast's MAE on the same origins and steps (relative MAE, not the classical MASE that
scales by in-sample errors); naive is 1.0.

Model choice: the one-standard-error rule. Each model's error at an origin is its mean absolute
error over the steps forecast from that origin; take the mean across origins and its standard
error. Find the best (lowest mean) model, then choose the simplest model whose mean error is within
one standard error of the best. Same rule for every company.

Prediction intervals are empirical: the half-width at step h is the conformal-style quantile
(rank ceil((n+1) x level)) of the chosen model's absolute backtest errors at that step, so the
interval is symmetric around the forecast. If a step has fewer than 20 errors, neighbouring steps
are pooled (window widened one step each side) until it has 20. Coverage is validated by
leave-one-origin-out: each origin's actuals are tested against intervals built from the other
origins' errors. Intervals are clipped at 0. Model-based Gaussian coverage is kept for comparison.

Run:   python src/forecast.py
"""
import itertools
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

try:
    from prophet import Prophet
    logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
    logging.getLogger("prophet").setLevel(logging.ERROR)
    HAVE_PROPHET = True
except ImportError:
    HAVE_PROPHET = False

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"

COMPANIES = ["OpenAI", "Anthropic", "Databricks", "NVIDIA"]
TARGETS = {"adjusted": "new_roles_adjusted", "unique": "new_roles_unique"}
HORIZON = 8
FIRST_ORIGIN = 14          # training weeks at the first backtest origin
MIN_ERRORS = 20            # backtest errors needed per step for an empirical interval (else pool steps)
MA_WINDOW = 4
ARIMA_GRID = list(itertools.product([0, 1, 2], [0, 1], [0, 1, 2]))     # (p, d, q)
SENSITIVITY_START = "2026-08-03"       # first week of August
Z = {80: 1.2816, 95: 1.96}
# fixed simplicity order, used by the one-standard-error rule
MODELS = ["naive", "ma4", "ses", "drift", "holt_damped", "arima"] + (["prophet"] if HAVE_PROPHET else [])


# ---------------------------------------------------------------- models: each returns (mean, sd) per step

def m_naive(y, h):
    s = np.std(np.diff(y), ddof=1)
    return np.full(h, y[-1]), s * np.sqrt(np.arange(1, h + 1))


def m_ma4(y, h):
    e = np.array([y[t] - y[t - MA_WINDOW:t].mean() for t in range(MA_WINDOW, len(y))])
    return np.full(h, y[-MA_WINDOW:].mean()), np.full(h, np.std(e, ddof=1))


def m_drift(y, h):
    n, steps = len(y), np.arange(1, h + 1)
    slope = (y[-1] - y[0]) / (n - 1)
    s = np.std(np.diff(y), ddof=1)
    return y[-1] + slope * steps, s * np.sqrt(steps * (1 + steps / (n - 1)))


def _ets(y, h, trend):
    ys = pd.Series(y, index=pd.date_range("2026-01-05", periods=len(y), freq="7D"))     # summary_frame needs a dated index
    fit = ETSModel(ys, error="add", trend=trend, damped_trend=trend is not None).fit(disp=False, maxiter=200)
    frame = fit.get_prediction(start=len(y), end=len(y) + h - 1).summary_frame(alpha=0.05)
    mean = frame["mean"].values
    return mean, (frame["pi_upper"].values - mean) / Z[95]


def m_ses(y, h):
    return _ets(y, h, None)


def m_holt(y, h):
    return _ets(y, h, "add")


def m_arima(y, h):
    best = None
    for p, d, q in ARIMA_GRID:
        try:
            fit = ARIMA(y, order=(p, d, q), trend="c" if d == 0 else "t").fit()
        except Exception:
            continue
        if best is None or fit.aic < best.aic:
            best = fit
    fc = best.get_forecast(h)
    return np.asarray(fc.predicted_mean), np.asarray(fc.se_mean)


def m_prophet(y, h):
    ds = pd.date_range(end="2026-01-01", periods=len(y), freq="7D")        # dates only set the spacing
    np.random.seed(0)                       # Prophet samples its intervals; fix the seed so fits repeat
    m = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False, interval_width=0.8)
    m.fit(pd.DataFrame({"ds": ds, "y": y}))
    f = m.predict(m.make_future_dataframe(h, freq="7D")).tail(h)
    return f["yhat"].values, (f["yhat_upper"].values - f["yhat_lower"].values) / (2 * Z[80])


FUNCS = {"naive": m_naive, "ma4": m_ma4, "drift": m_drift, "ses": m_ses, "holt_damped": m_holt,
         "arima": m_arima, "prophet": m_prophet if HAVE_PROPHET else None}


def run_model(name, y, h):
    """Forecast h steps; returns dict of arrays (mean, lo/hi at 80 and 95, clipped at 0) or None on failure."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mean, sd = FUNCS[name](np.asarray(y, float), h)
    except Exception:
        return None
    if not (np.all(np.isfinite(mean)) and np.all(np.isfinite(sd))):
        return None
    out = {"mean": np.clip(mean, 0, None)}
    for lvl, z in Z.items():
        out[f"lo{lvl}"] = np.clip(mean - z * sd, 0, None)
        out[f"hi{lvl}"] = np.clip(mean + z * sd, 0, None)
    return out


# ---------------------------------------------------------------- backtest

def forecast_at_origin(y, t, h):
    """Forecasts from the first t points only. The slice is taken here so nothing after t can leak in."""
    train = np.asarray(y[:t], float)
    return {m: run_model(m, train, h) for m in MODELS}


def backtest(y):
    """Rolling origin, expanding window. Returns long records (origin, step, model, actual, forecasts)."""
    rows = []
    for t in range(FIRST_ORIGIN, len(y)):
        h = min(HORIZON, len(y) - t)
        for m, f in forecast_at_origin(y, t, h).items():
            if f is None:
                continue
            for k in range(h):
                rows.append(dict(origin=t, step=k + 1, model=m, actual=y[t + k], **{key: v[k] for key, v in f.items()}))
    return pd.DataFrame(rows)


def halfwidth(err, step, level, exclude_origin=None):
    """Empirical interval half-width at a step: quantile of absolute backtest errors, pooling
    neighbouring steps until at least MIN_ERRORS errors. err is indexed by (origin, step).
    Returns (half-width, number of errors used)."""
    steps, origins = err.index.get_level_values("step"), err.index.get_level_values("origin")
    counts = steps.value_counts()
    w = 0
    while True:
        lo, hi = max(1, step - w), min(HORIZON, step + w)
        if sum(counts.get(k, 0) for k in range(lo, hi + 1)) >= MIN_ERRORS or (lo == 1 and hi == HORIZON):
            break
        w += 1
    mask = (steps >= lo) & (steps <= hi)
    if exclude_origin is not None:
        mask &= origins != exclude_origin
    e = np.sort(err.values[mask])
    k = min(int(np.ceil((len(e) + 1) * level)), len(e))        # conformal rank
    return e[k - 1], len(e)


def loo_coverage(err, level):
    """Leave-one-origin-out coverage of empirical intervals."""
    hits = [err.loc[(o, h)] <= halfwidth(err, h, level, exclude_origin=o)[0] for o, h in err.index]
    return float(np.mean(hits))


def score(bt):
    """MAE, relative MAE against naive on identical origins and steps, per-origin error and its SE,
    and interval coverage (model-based Gaussian, and empirical leave-one-origin-out)."""
    naive = bt[bt.model == "naive"].set_index(["origin", "step"])
    out = []
    for m, g in bt.groupby("model"):
        g = g.set_index(["origin", "step"])
        err = (g.actual - g["mean"]).abs()
        base = (naive.actual - naive["mean"]).abs().reindex(g.index)
        per_origin = err.groupby(level="origin").mean()
        out.append(dict(model=m, mae=err.mean(), rel_mae=err.sum() / base.sum(),
                        origin_mae=per_origin.mean(), origin_mae_se=per_origin.std(ddof=1) / np.sqrt(len(per_origin)),
                        coverage80_model=((g.actual >= g.lo80) & (g.actual <= g.hi80)).mean(),
                        coverage95_model=((g.actual >= g.lo95) & (g.actual <= g.hi95)).mean(),
                        coverage80_empirical=loo_coverage(err, 0.80), coverage95_empirical=loo_coverage(err, 0.95),
                        n_origins=len(per_origin), n_forecasts=len(g)))
    return pd.DataFrame(out)


def one_se_choice(sc):
    """Simplest model whose mean per-origin error is within one standard error of the best model."""
    sc = sc.set_index("model").reindex(MODELS)
    best = sc.origin_mae.idxmin()
    threshold = sc.loc[best, "origin_mae"] + sc.loc[best, "origin_mae_se"]
    within = sc.origin_mae <= threshold
    return next(m for m in MODELS if within[m]), best, threshold, within


# ---------------------------------------------------------------- main

def load():
    w = pd.read_csv(P / "weekly_postings.csv", parse_dates=["week_start"])
    series = {}
    for c in COMPANIES:
        g = w[w.company_name == c].dropna(subset=["new_roles_unique"]).sort_values("week_start")
        series[c] = g.set_index("week_start")[list(TARGETS.values())].astype(float)
    return series


def main():
    series = load()
    metrics, forecasts, sens = [], [], []
    chosen, best_model, errors = {}, {}, {}
    for c, df in series.items():
        for tname, col in TARGETS.items():
            bt = backtest(df[col].values)
            sc = score(bt)
            pick, best, thr, within = one_se_choice(sc)
            sc.insert(0, "target", tname)
            sc.insert(0, "company_name", c)
            sc["best_model"] = sc.model == best
            sc["one_se_threshold"] = thr
            sc["within_1se_of_best"] = sc.model.map(within)
            sc["chosen"] = sc.model == pick
            metrics.append(sc)
            chosen[(c, tname)], best_model[(c, tname)] = pick, best
            b = bt[bt.model == pick].set_index(["origin", "step"])
            errors[(c, tname)] = (b.actual - b["mean"]).abs()
    metrics = pd.concat(metrics, ignore_index=True)
    metrics = metrics.round({"mae": 2, "rel_mae": 3, "origin_mae": 2, "origin_mae_se": 2, "one_se_threshold": 2,
                             "coverage80_model": 3, "coverage95_model": 3, "coverage80_empirical": 3,
                             "coverage95_empirical": 3})

    for c, df in series.items():
        y, weeks = df["new_roles_adjusted"].values, df.index
        model = chosen[(c, "adjusted")]
        future = [weeks[-1] + pd.Timedelta(weeks=k) for k in range(1, HORIZON + 1)]
        f = run_model(model, y, HORIZON)
        for k in range(HORIZON):
            hw80, n = halfwidth(errors[(c, "adjusted")], k + 1, 0.80)
            hw95, _ = halfwidth(errors[(c, "adjusted")], k + 1, 0.95)
            fk = f["mean"][k]
            forecasts.append(dict(company_name=c, step=k + 1, week_start=future[k].date(), model=model, forecast=fk,
                                  lo80=max(fk - hw80, 0), hi80=fk + hw80, lo95=max(fk - hw95, 0), hi95=fk + hw95,
                                  n_errors=n))
        # sensitivity: unique-roles target, and a refit on August onwards (same model family)
        scenarios = {"base": y, "unique_target": df["new_roles_unique"].values,
                     "from_august": df.loc[df.index >= SENSITIVITY_START, "new_roles_adjusted"].values}
        for name, ys in scenarios.items():
            fs = f if name == "base" else run_model(model, ys, HORIZON)
            for k in range(HORIZON):
                sens.append(dict(company_name=c, scenario=name, model=model, step=k + 1,
                                 week_start=future[k].date(), n_weeks_fitted=len(ys),
                                 forecast=fs["mean"][k] if fs else np.nan, base_forecast=f["mean"][k]))
    forecasts = pd.DataFrame(forecasts).round(2)
    sens = pd.DataFrame(sens)
    sens["diff_pct"] = ((sens.forecast / sens.base_forecast - 1) * 100).round(1)
    sens["forecast"] = sens.forecast.round(2)
    sens["base_forecast"] = sens.base_forecast.round(2)

    vel = pd.read_csv(P / "velocity_summary.csv").set_index("company_name")
    flows = pd.read_csv(P / "snapshot_flows.csv")
    n_int = flows[~flows.is_baseline.astype(bool)].groupby("company_name").size()
    cc = []
    for c in COMPANIES:
        nxt = forecasts[(forecasts.company_name == c) & (forecasts.step <= 2)].forecast.mean()
        cc.append(dict(company_name=c, model=chosen[(c, "adjusted")], forecast_next2_mean=round(nxt, 1),
                       snapshot_opened_per_week=vel.loc[c, "opened_per_week"],
                       ratio=round(nxt / vel.loc[c, "opened_per_week"], 2), flows_provisional=bool(n_int[c] == 1)))
    cc = pd.DataFrame(cc)

    forecasts.to_csv(P / "forecasts.csv", index=False)
    metrics.to_csv(P / "backtest_metrics.csv", index=False)
    sens.to_csv(P / "forecast_sensitivity.csv", index=False)
    cc.to_csv(P / "forecast_crosscheck.csv", index=False)

    report(series, metrics, forecasts, sens, cc)
    checks(series, metrics, forecasts)


def report(series, metrics, forecasts, sens, cc):
    print(f"Models: {', '.join(MODELS)}{'' if HAVE_PROPHET else ' (Prophet not installed, skipped)'}")
    print("Weeks per company:", {c: len(d) for c, d in series.items()})
    for tname in TARGETS:
        m = metrics[metrics.target == tname]
        print(f"\nBacktest relative MAE vs naive (target {tname}):")
        print(m.pivot(index="model", columns="company_name", values="rel_mae")[COMPANIES].reindex(MODELS).to_string())
        print("best:  ", m[m.best_model].set_index("company_name").model.reindex(COMPANIES).to_dict())
        print("chosen (one-SE):", m[m.chosen].set_index("company_name").model.reindex(COMPANIES).to_dict())
        cov = m[m.chosen].set_index("company_name").reindex(COMPANIES)[
            ["coverage80_model", "coverage80_empirical", "coverage95_model", "coverage95_empirical"]]
        print("coverage of the chosen model:\n" + cov.to_string())
    print("\nForecast cross-check:\n", cc.to_string(index=False))


def checks(series, metrics, forecasts):
    print("\nSanity checks")
    ok = True

    def check(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        print(f"  [{'ok' if passed else 'FAIL'}] {name} {detail}")

    check("same horizon for all four", forecasts.groupby("company_name").step.max().eq(HORIZON).all()
          and forecasts.groupby("company_name").size().eq(HORIZON).all())
    sets = {c: frozenset(g.model) for c, g in metrics[metrics.target == "adjusted"].groupby("company_name")}
    check("same candidate models for all four", len(set(sets.values())) == 1 and set(sets[COMPANIES[0]]) == set(MODELS))
    cols = ["forecast", "lo80", "hi80", "lo95", "hi95"]
    check("no negative forecasts or bounds", (forecasts[cols] >= 0).all().all())
    check("intervals contain the point forecast", ((forecasts.lo95 <= forecasts.lo80) & (forecasts.lo80 <= forecasts.forecast)
                                                  & (forecasts.forecast <= forecasts.hi80) & (forecasts.hi80 <= forecasts.hi95)).all())
    check("exactly one chosen model per company and target", metrics[metrics.chosen].groupby(["company_name", "target"]).size().eq(1).all()
          and len(metrics[metrics.chosen]) == len(COMPANIES) * len(TARGETS))
    check("weekly series contiguous, no gaps", all((d.index.to_series().diff().dropna() == pd.Timedelta(weeks=1)).all() for d in series.values()))
    # leakage: change every value after the origin; forecasts made at that origin must not change
    leak = []
    for c, d in series.items():
        y = d["new_roles_adjusted"].values
        t = max(FIRST_ORIGIN, len(y) - 4)
        scrambled = y.copy()
        scrambled[t:] = scrambled[t:] * 7 + 500
        a, b = forecast_at_origin(y, t, 4), forecast_at_origin(scrambled, t, 4)
        for m in MODELS:
            same = (a[m] is None and b[m] is None) or (a[m] is not None and b[m] is not None
                                                        and all(np.allclose(a[m][k], b[m][k], rtol=1e-6, atol=1e-6) for k in a[m]))
            if not same:
                leak.append((c, m))
    check("backtest never uses data after its origin", not leak, f"(forecasts changed for {leak})" if leak else "(all models, all companies)")
    n_fc = metrics[metrics.target == "adjusted"].pivot(index="model", columns="company_name", values="n_forecasts")
    check("every interval built from at least 20 backtest errors", (forecasts.n_errors >= MIN_ERRORS).all(),
          f"(min {forecasts.n_errors.min()})")
    check("every model produced forecasts at every origin", (n_fc.eq(n_fc.loc["naive"], axis=1)).all().all(),
          "" if (n_fc.eq(n_fc.loc["naive"], axis=1)).all().all() else f"\n{n_fc.to_string()}")
    if not ok:
        raise SystemExit("sanity check failed")


if __name__ == "__main__":
    main()
