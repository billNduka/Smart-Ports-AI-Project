"""
Multi-seed experiment runner + schedule validator for the Berth Allocation project.

Run from the project root:
    python -m src.experiments.run_experiments                  # 30 seeds, default scenarios
    python -m src.experiments.run_experiments --seeds 10 --time-limit 5
    python -m src.experiments.run_experiments --scenarios "15:3:2.0,50:4:1.45" --ensure-coverage

Scenario format:  vessels:berths:arrival_rate_per_hour

Outputs (in experiments/results/):
    runs.csv      one row per (scenario, seed)
    summary.csv   one row per scenario, mean / SD / 95% CI / win-rate
    summary.md    the same table, ready to paste into the thesis or README
"""
import argparse
import copy
import csv
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.data_simulator import IoTSimulator
from src.services.schedulers.fcfs_scheduler import FCFSScheduler
from src.services.schedulers.ai_scheduler import AIScheduler
from src.services.metrics_engine import MetricsCalculator

DEFAULT_SCENARIOS = "15:3:2.0,30:3:1.5,50:4:1.45,50:3:2.5,50:6:1.45"
OUT_DIR = Path(__file__).resolve().parent / "results"


# --------------------------------------------------------------------------
# Validation: independent check that a schedule is physically feasible
# --------------------------------------------------------------------------
def validate_schedule(vessels, berths, assignments, tol_s=1.0):
    """Return a list of human-readable violations (empty list = valid).

    `berths` must be the ORIGINAL berths (initial available_from), not ones
    already mutated by a scheduler.
    """
    errors = []
    vmap = {v.vessel_id: v for v in vessels}
    bmap = {b.berth_id: b for b in berths}
    seen = set()
    per_berth = {}

    for a in assignments:
        v, b = vmap.get(a.vessel_id), bmap.get(a.berth_id)
        if v is None or b is None:
            errors.append(f"unknown vessel/berth id in assignment {a}")
            continue
        if a.vessel_id in seen:
            errors.append(f"{a.vessel_id} assigned more than once")
        seen.add(a.vessel_id)

        if not v.is_compatible_with_berth(b.capacity, b.compatible_cargo_types):
            errors.append(f"{v.vessel_id} placed on incompatible {b.berth_id}")

        early = (v.arrival_time - a.start_time).total_seconds()
        if early > tol_s:
            errors.append(f"{v.vessel_id} starts {early:.0f}s BEFORE it arrives")

        early_b = (b.available_from - a.start_time).total_seconds()
        if early_b > tol_s:
            errors.append(f"{v.vessel_id} starts {early_b:.0f}s before {b.berth_id} is available")

        dur_h = (a.end_time - a.start_time).total_seconds() / 3600.0
        if abs(dur_h - v.handling_time) * 3600.0 > tol_s:
            errors.append(
                f"{v.vessel_id} service {dur_h:.4f}h != handling_time {v.handling_time:.4f}h"
            )
        per_berth.setdefault(a.berth_id, []).append(a)

    for bid, lst in per_berth.items():
        lst.sort(key=lambda x: x.start_time)
        for prev, cur in zip(lst, lst[1:]):
            if (prev.end_time - cur.start_time).total_seconds() > tol_s:
                errors.append(f"overlap on {bid}: {prev.vessel_id} and {cur.vessel_id}")

    # Every vessel that CAN be served must be served
    for v in vessels:
        has_berth = any(
            v.is_compatible_with_berth(b.capacity, b.compatible_cargo_types) for b in berths
        )
        if has_berth and v.vessel_id not in seen:
            errors.append(f"{v.vessel_id} has a compatible berth but was not scheduled")
    return errors


# --------------------------------------------------------------------------
# One simulation run
# --------------------------------------------------------------------------
def waits_hours(vessels, assignments):
    vmap = {v.vessel_id: v for v in vessels}
    # NOT clamped at 0: a negative wait means the schedule is invalid and the
    # validator will flag it.
    return [
        (a.start_time - vmap[a.vessel_id].arrival_time).total_seconds() / 3600.0
        for a in assignments
    ]


def makespan_hours(vessels, assignments):
    if not assignments:
        return 0.0
    first = min(v.arrival_time for v in vessels)
    return (max(a.end_time for a in assignments) - first).total_seconds() / 3600.0


def run_one(scenario, seed, time_limit, ensure_coverage):
    n_vessels, n_berths, rate = scenario
    sim = IoTSimulator(seed=seed)
    berth_kwargs = {"ensure_coverage": True} if ensure_coverage else {}
    berths = sim.generate_berths(n_berths, **berth_kwargs)
    vessels = sim.generate_vessels(n_vessels, arrival_rate_per_hour=rate)

    fcfs_assign = FCFSScheduler().schedule(vessels, copy.deepcopy(berths))

    ai = AIScheduler(time_limit_seconds=time_limit)
    t0 = time.time()
    ai_assign = ai.schedule(vessels, copy.deepcopy(berths))
    ai_seconds = time.time() - t0

    fcfs_err = validate_schedule(vessels, berths, fcfs_assign)
    ai_err = validate_schedule(vessels, berths, ai_assign)

    fw, aw = waits_hours(vessels, fcfs_assign), waits_hours(vessels, ai_assign)
    fm = MetricsCalculator.calculate_metrics(vessels, berths, fcfs_assign)
    am = MetricsCalculator.calculate_metrics(vessels, berths, ai_assign)
    f_avg = sum(fw) / len(fw) if fw else 0.0
    a_avg = sum(aw) / len(aw) if aw else 0.0

    return {
        "vessels": n_vessels, "berths": n_berths, "rate": rate, "seed": seed,
        "served_fcfs": len(fcfs_assign), "served_ai": len(ai_assign),
        "unserved": n_vessels - len(fcfs_assign),
        "fcfs_avg_wait_h": f_avg, "ai_avg_wait_h": a_avg,
        "fcfs_max_wait_h": max(fw, default=0.0), "ai_max_wait_h": max(aw, default=0.0),
        "fcfs_util_pct": fm.berth_utilization_pct, "ai_util_pct": am.berth_utilization_pct,
        "fcfs_makespan_h": makespan_hours(vessels, fcfs_assign),
        "ai_makespan_h": makespan_hours(vessels, ai_assign),
        "ai_solver_status": getattr(ai, "last_status", "n/a"),
        "ai_solve_s": round(getattr(ai, "last_solve_seconds", ai_seconds), 2),
        "fcfs_violations": len(fcfs_err), "ai_violations": len(ai_err),
        "first_violation": (ai_err or fcfs_err or [""])[0],
    }


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
def t_crit(df):
    try:
        from scipy.stats import t
        return float(t.ppf(0.975, df))
    except Exception:
        return 1.96  # normal approximation


def mean_ci(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    m = statistics.fmean(xs)
    if n < 2:
        return m, 0.0, 0.0
    sd = statistics.stdev(xs)
    half = t_crit(n - 1) * sd / math.sqrt(n)
    return m, sd, half


def summarise(rows):
    out = []
    scen = sorted({(r["vessels"], r["berths"], r["rate"]) for r in rows})
    for s in scen:
        rs = [r for r in rows if (r["vessels"], r["berths"], r["rate"]) == s and r["served_fcfs"] > 0]
        if not rs:
            continue
        diff = [r["fcfs_avg_wait_h"] - r["ai_avg_wait_h"] for r in rs]            # hours saved
        pct = [100.0 * d / r["fcfs_avg_wait_h"] for d, r in zip(diff, rs) if r["fcfs_avg_wait_h"] > 1e-9]
        d_m, d_sd, d_ci = mean_ci(diff)
        p_m, p_sd, p_ci = mean_ci(pct)
        out.append({
            "vessels": s[0], "berths": s[1], "rate": s[2], "runs": len(rs),
            "avg_unserved": round(statistics.fmean(r["unserved"] for r in rs), 1),
            "fcfs_avg_wait_h": round(statistics.fmean(r["fcfs_avg_wait_h"] for r in rs), 2),
            "ai_avg_wait_h": round(statistics.fmean(r["ai_avg_wait_h"] for r in rs), 2),
            "saved_h_mean": round(d_m, 2), "saved_h_ci95": round(d_ci, 2),
            "saved_pct_mean": round(p_m, 1), "saved_pct_sd": round(p_sd, 1), "saved_pct_ci95": round(p_ci, 1),
            "ai_wins": sum(1 for d in diff if d > 1e-6),
            "ties": sum(1 for d in diff if abs(d) <= 1e-6),
            "ai_losses": sum(1 for d in diff if d < -1e-6),
            "fcfs_max_wait_h": round(statistics.fmean(r["fcfs_max_wait_h"] for r in rs), 2),
            "ai_max_wait_h": round(statistics.fmean(r["ai_max_wait_h"] for r in rs), 2),
            "not_optimal_runs": sum(1 for r in rs if r["ai_solver_status"] not in ("OPTIMAL", "n/a")),
            "invalid_runs": sum(1 for r in rs if r["fcfs_violations"] or r["ai_violations"]),
        })
    return out


def to_markdown(summary):
    hdr = ("| Vessels | Berths | Rate/hr | Runs | Unserved (avg) | FCFS wait (h) | AI wait (h) | "
           "Saved (h, 95% CI) | Saved (%, 95% CI) | AI win/tie/loss | Max wait FCFS→AI (h) | Not-optimal | Invalid |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    rows = ""
    for s in summary:
        rows += (f"| {s['vessels']} | {s['berths']} | {s['rate']} | {s['runs']} | {s['avg_unserved']} | "
                 f"{s['fcfs_avg_wait_h']} | {s['ai_avg_wait_h']} | "
                 f"{s['saved_h_mean']} ± {s['saved_h_ci95']} | {s['saved_pct_mean']} ± {s['saved_pct_ci95']} | "
                 f"{s['ai_wins']}/{s['ties']}/{s['ai_losses']} | {s['fcfs_max_wait_h']}→{s['ai_max_wait_h']} | "
                 f"{s['not_optimal_runs']} | {s['invalid_runs']} |\n")
    return hdr + rows


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    ap.add_argument("--seeds", type=int, default=30, help="number of seeds per scenario (1..N)")
    ap.add_argument("--time-limit", type=float, default=10.0, help="CP-SAT seconds per run")
    ap.add_argument("--ensure-coverage", action="store_true",
                    help="every cargo type has a berth and the biggest berth fits the biggest ship")
    args = ap.parse_args()

    scenarios = []
    for chunk in args.scenarios.split(","):
        v, b, r = chunk.strip().split(":")
        scenarios.append((int(v), int(b), float(r)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for sc in scenarios:
        for seed in range(1, args.seeds + 1):
            row = run_one(sc, seed, args.time_limit, args.ensure_coverage)
            rows.append(row)
            flag = "  <-- INVALID: " + row["first_violation"] if (row["fcfs_violations"] or row["ai_violations"]) else ""
            print(f"{sc} seed={seed:>2} served {row['served_fcfs']}/{sc[0]} "
                  f"FCFS {row['fcfs_avg_wait_h']:.2f}h  AI {row['ai_avg_wait_h']:.2f}h "
                  f"[{row['ai_solver_status']}]{flag}", flush=True)

    summary = summarise(rows)
    write_csv(OUT_DIR / "runs.csv", rows)
    write_csv(OUT_DIR / "summary.csv", summary)
    md = to_markdown(summary)
    (OUT_DIR / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    bad = sum(1 for r in rows if r["fcfs_violations"] or r["ai_violations"])
    print(f"Runs with schedule violations: {bad}/{len(rows)}  (details: runs.csv -> first_violation)")


if __name__ == "__main__":
    main()