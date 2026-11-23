"""
Task 7: demand forecasting.

Reads  data/processed/weekly_postings.csv, snapshot_flows.csv, velocity_summary.csv
       (Task 5; no scraping, no description text)
Writes data/processed/ (all committed):
  forecasts.csv             company_name, step, week_start, model, forecast, lo80, hi80, lo95, hi95
  backtest_metrics.csv      company x target x model: MAE, MASE, coverage, n_origins, chosen
  forecast_sensitivity.csv  company x scenario x week: base forecast vs the unique-roles target and
                            vs a refit on August onwards
  forecast_crosscheck.csv   forecast level for the next 2 weeks vs the snapshot opened_per_week

Target: weekly new_roles_adjusted (survivorship-adjusted unique new roles). Sensitivity targets:
new_roles_unique, and the same model refitted on August onwards (weeks before about August are
floors because the survivorship correction is capped at 3x).

Horizon: 8 steps (weeks) ahead for every company, counted from that company's last complete week.
NVIDIA's snapshots lag the others, so its last complete week is one week earlier.

Candidate models, identical for every company: naive (last value), 4-week moving average, drift,
simple exponential smoothing, Holt with damped trend, ARIMA (small order grid chosen by AIC) and
Prophet (default settings, seasonality off; skipped if it is not installed). No seasonal models and
no deep learning: 26 weekly points cannot support them.

Backtest: rolling origin, expanding window, first origin after 14 weeks, each origin forecasts up
to 8 weeks ahead (fewer near the end of the data). MAE is pooled over origins and steps. MASE is
the model's MAE divided by the naive forecast's MAE on the same origins and steps, so naive is 1.0
and a model below 1.0 beats naive. The chosen model has the lowest MASE, but it only counts as
beating naive if its MASE is below 0.95 (a 5% margin, because 12 origins cannot separate smaller
differences, and a smoother that collapses to naive scores about 1.0). Otherwise nothing beat
naive and naive is used. Prediction intervals are Gaussian around each model's forecast
(each model's own standard error where it has one) and clipped at 0; coverage is measured in the
backtest.

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
NAIVE_MARGIN = 0.95        # a model must have MASE below this to be chosen over naive
MA_WINDOW = 4
ARIMA_GRID = list(itertools.product([0, 1, 2], [0, 1], [0, 1, 2]))     # (p, d, q)
SENSITIVITY_START = "2026-08-03"       # first week of August
Z = {80: 1.2816, 95: 1.96}
MODELS = ["naive", "ma4", "drift", "ses", "holt_damped", "arima"] + (["prophet"] if HAVE_PROPHET else [])


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


def score(bt):
    """MAE, MASE against naive on identical origins and steps, interval coverage."""
    naive = bt[bt.model == "naive"].set_index(["origin", "step"])
    out = []
    for m, g in bt.groupby("model"):
        g = g.set_index(["origin", "step"])
        err = (g.actual - g["mean"]).abs()
        base = (naive.actual - naive["mean"]).abs().reindex(g.index)
        out.append(dict(model=m, mae=err.mean(), mase=err.sum() / base.sum(),
                        coverage80=((g.actual >= g.lo80) & (g.actual <= g.hi80)).mean(),
                        coverage95=((g.actual >= g.lo95) & (g.actual <= g.hi95)).mean(),
                        n_origins=g.index.get_level_values("origin").nunique(), n_forecasts=len(g)))
    return pd.DataFrame(out)


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
    chosen = {}
    for c, df in series.items():
        for tname, col in TARGETS.items():
            y = df[col].values
            sc = score(backtest(y))
            sc.insert(0, "target", tname)
            sc.insert(0, "company_name", c)
            best = sc.loc[sc.mase.idxmin(), "model"]          # ties go to the earlier (simpler) model
            if sc.mase.min() >= NAIVE_MARGIN:
                best = "naive"                                # nothing beat naive by the margin
            sc["chosen"] = sc.model == best
            metrics.append(sc)
            chosen[(c, tname)] = best
    metrics = pd.concat(metrics, ignore_index=True)
    metrics["beats_naive"] = metrics.mase < NAIVE_MARGIN
    metrics = metrics.round({"mae": 2, "mase": 3, "coverage80": 3, "coverage95": 3})

    for c, df in series.items():
        y, weeks = df["new_roles_adjusted"].values, df.index
        model = chosen[(c, "adjusted")]
        future = [weeks[-1] + pd.Timedelta(weeks=k) for k in range(1, HORIZON + 1)]
        f = run_model(model, y, HORIZON)
        for k in range(HORIZON):
            forecasts.append(dict(company_name=c, step=k + 1, week_start=future[k].date(), model=model,
                                  forecast=f["mean"][k], lo80=f["lo80"][k], hi80=f["hi80"][k],
                                  lo95=f["lo95"][k], hi95=f["hi95"][k]))
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
        print(f"\nBacktest MASE vs naive (target {tname}):")
        print(m.pivot(index="model", columns="company_name", values="mase")[COMPANIES].reindex(MODELS).to_string())
        print("chosen:", m[m.chosen].set_index("company_name").model.reindex(COMPANIES).to_dict())
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
    check("every model produced forecasts at every origin", (n_fc.eq(n_fc.loc["naive"], axis=1)).all().all(),
          "" if (n_fc.eq(n_fc.loc["naive"], axis=1)).all().all() else f"\n{n_fc.to_string()}")
    if not ok:
        raise SystemExit("sanity check failed")


if __name__ == "__main__":
    main()
