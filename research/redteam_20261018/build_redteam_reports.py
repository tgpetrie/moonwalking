"""NEW COPY/ADAPTATION of evaluate_resolution_costs.py: internal evidence reports.
Numerical results and public market samples stay under ignored .runtime; only
code, frozen source scripts and method documentation belong in Git.
"""

import datetime, hashlib, json, pathlib, sqlite3, sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
RUN = pathlib.Path(".runtime/redteam_20261018").resolve()
RESULTS = RUN / "results_final/tests.jsonl"
REPORTS = RUN / (sys.argv[1] if len(sys.argv) > 1 else "reports_final")
if REPORTS.resolve().parent != RUN:
    raise ValueError("Reports must stay inside own runtime directory")


def link(path, line=1, label=None):
    p = pathlib.Path(path).resolve()
    return f"[{label or p.name} line {line}](<{p.as_posix()}:{line}>)"


def source(name, needle):
    p = ROOT / "source_scripts" / name
    for i, text in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if needle in text:
            return link(p, i)
    raise ValueError((name, needle))


def code(needle):
    for i, text in enumerate(
        (ROOT / "audit_experiments.py").read_text().splitlines(), 1
    ):
        if needle in text:
            return link(ROOT / "audit_experiments.py", i)
    raise ValueError(needle)


def fmt(v):
    return f"{v:+.3f}"


def ci(row):
    return "[" + ", ".join(fmt(v) for v in row["week"]["percentile_95"]) + "]"


def common_market_check():
    # Explicitly restrict raw and adjusted effects to the identical >=20-peer cohort.
    db = sqlite3.connect(
        (RUN / "data/candle_replay.sqlite").as_uri() + "?mode=ro&immutable=1", uri=True
    )
    rows = db.execute(
        "select product_id,ts,range_pos,momentum,vol_ratio,status,atr_pct,ret24 from replay"
    ).fetchall()
    db.close()
    p = np.array([r[0] for r in rows])
    t = np.array([r[1] for r in rows])
    rp = np.array([r[2] for r in rows])
    mom = np.array([r[3] if r[3] is not None else np.nan for r in rows])
    vol = np.array([r[4] if r[4] is not None else np.nan for r in rows])
    status = np.array([r[5] for r in rows])
    atr = np.array([r[6] for r in rows])
    ret = np.array([r[7] for r in rows])
    _, pi = np.unique(p, return_inverse=True)
    coinmean = np.bincount(pi, weights=ret) / np.bincount(pi)
    _, ti = np.unique(t, return_inverse=True)
    n = np.bincount(ti)
    total = np.bincount(ti, weights=ret * atr)
    neutral = (ret * atr - (total[ti] - ret * atr) / np.maximum(n[ti] - 1, 1)) / atr
    _, wi = np.unique(
        [
            datetime.datetime.fromtimestamp(int(v), datetime.timezone.utc).strftime(
                "%G-W%V"
            )
            for v in t
        ],
        return_inverse=True,
    )
    G = wi.max() + 1
    findings = {}
    conditions = {
        "top_85_vs_rest": (rp >= 85, rp < 85),
        "high_status_vs_clear": (status == "high", status == "clear"),
        "down_volume_1.5": ((mom < 0) & (vol >= 1.5), (mom < 0) & (vol < 1.5)),
    }
    for name, (a, b) in conditions.items():
        a = a & (n[ti] >= 21)
        b = b & (n[ti] >= 21)
        rng = np.random.default_rng(13)
        ix = rng.integers(0, G, (2000, G))
        vals = {}
        for label, x in [
            ("coin_demeaned_same_cohort", ret - coinmean[pi]),
            ("leave_one_coin_out_market_neutral", neutral),
        ]:
            sa = np.bincount(wi, weights=np.where(a, x, 0), minlength=G)
            na = np.bincount(wi, weights=a, minlength=G)
            sb = np.bincount(wi, weights=np.where(b, x, 0), minlength=G)
            nb = np.bincount(wi, weights=b, minlength=G)
            valid = (na[ix].sum(1) > 0) & (nb[ix].sum(1) > 0)
            jj = ix[valid]
            draws = sa[jj].sum(1) / na[jj].sum(1) - sb[jj].sum(1) / nb[jj].sum(1)
            vals[label] = {
                "effect_ATR": float(x[a].mean() - x[b].mean()),
                "week_bootstrap_95": np.quantile(draws, [0.025, 0.975]).tolist(),
            }
        findings[name] = {
            "treated": int(a.sum()),
            "control": int(b.sum()),
            "weeks": int(G),
            **vals,
        }
    path = REPORTS / "market_common_cohort.jsonl"
    with path.open("x", encoding="utf-8") as f:
        for name, result in findings.items():
            f.write(
                json.dumps(
                    {
                        "test": name,
                        "method": "Same >=20-other-coin cohort; benchmark excludes the target coin; whole-ISO-week bootstrap, 2000 draws, seed13",
                        "result": result,
                    }
                )
                + "\n"
            )
    return findings, path


def write_audit():
    records = {}
    line_numbers = {}
    for i, line in enumerate(RESULTS.read_text().splitlines(), 1):
        row = json.loads(line)
        records[row["test"]] = row
        line_numbers[row["test"]] = i
    market, market_path = common_market_check()
    rows = [
        "# Internal red-team review — 2026-10-18",
        "",
        "Assessment: needs revision before strong inferential or threshold claims. The broad no-demonstrated-edge conclusion survives these checks; some earlier sell-side interpretations do not survive market-adjusted comparisons. This is an internal review, not new out-of-sample confirmation. "
        + link(RESULTS, line_numbers["baseline_replication"])
        + " "
        + link(market_path, 1),
        "",
        "Scope: tests use byte-verified, read-only copies of the completed reconstruction and replay databases, plus this branch’s frozen market-only export and four-coin candles. The active year-long archive and production are not opened. Copy provenance: "
        + link(RUN / "copy_manifest.json", 1)
        + ". SQLite path enforcement: "
        + code("def ro(")
        + ".",
        "All intervals below are exploratory with few market blocks. A percentile interval over six weeks is not a reliable equivalence guarantee. Point estimates, population changes, and uncertainty are reported together. Bootstrap method: "
        + code("def boot(")
        + ".",
        "The hypothetical costs are assumptions, not measured account fees. R is the source 1-ATR stop unit; 24h labels retain the source’s actual 23–24h timing. "
        + source("recon.py", "NPATH =")
        + " "
        + source("recon.py", "COST_PCT ="),
        "",
        "## Tests, results and effect on the conclusion",
        "",
    ]
    for name, record in records.items():
        r = record["result"]
        reference = link(RESULTS, line_numbers[name])
        methodref = code('"' + name + '"')
        rows += [f"### {name}", "", f'Method: {record["method"]}. {methodref}', ""]
        if name == "baseline_replication":
            rows += [
                f'Result: {r["matched"]:,} matched / {r["unmatched"]:,} unmatched of {r["attempted"]:,} attempted; median {r["median_controls"]:.0f} controls. Confidence join coverage {r["confidence_join_coverage"]:.0%}.',
                "",
                "| Direction | n | Excess R | Exploratory ISO-week 95% interval |",
                "|---|---:|---:|---|",
            ]
            for d, z in r["estimates"].items():
                rows.append(
                    f'| {d} | {z["n"]:,} | {fmt(z["net_R_excess"])} | {ci(z)} |'
                )
            rows += [
                "",
                "The source result reproduces; this does not establish zero effect or independent trades. "
                + source("matched_control.py", "m = (np.abs"),
            ]
        elif name == "lookahead_future_controls":
            rows += [
                "| Policy / direction | n | Excess R | Exploratory week interval |",
                "|---|---:|---:|---|",
            ]
            for policy in ("symmetric", "past_only"):
                for d, z in r[policy].items():
                    rows.append(
                        f'| {policy} / {d} | {z["n"]:,} | {fmt(z["net_R_excess"])} | {ci(z)} |'
                    )
            rows += [
                "",
                "No positive advantage is established. Past-only matching changes effect size and matchability, and its down interval permits a useful positive effect. Symmetric future controls are not inherently feature lookahead for a retrospective comparison, but are unavailable as an online baseline. "
                + source("matched_control.py", "lo, hi = np.searchsorted"),
            ]
        elif name == "dedupe_selection":
            rows += [
                "| Dedupe policy | Matched | Up excess R | Down excess R |",
                "|---|---:|---:|---:|",
            ]
            for policy, z in r.items():
                rows.append(
                    f'| {policy} | {z["matched"]:,} | {fmt(z["estimates"]["up"]["net_R_excess"])} | {fmt(z["estimates"]["down"]["net_R_excess"])} |'
                )
            rows += [
                "",
                "The original insertion-order selection equals explicit earliest on this snapshot. Latest and max-confidence choices change estimates; they are hindsight selection sensitivities, not executable entries unless the block is first allowed to close. The 24h spacing policy leaves only a fraction of the original sample. Nominal significance after choosing among these policies is not confirmatory. Spacing is per coin/direction; opposite directions and correlated coins still overlap. "
                + source("matched_control.py", "k = (p, d, lab, ts // 14400)")
                + " "
                + source("matched_control.py", "select product_id, ts, label"),
            ]
        elif name == "overlap_and_reuse":
            rows += [
                f'{r["control_pairs"]:,} control assignments reuse {r["distinct_controls_used"]:,} distinct controls; median reuse {r["median_reuse"]:.0f}, maximum {r["maximum_reuse"]}.',
                "",
                "| Direction | IID SE | Day-cluster SE | ISO-week SE |",
                "|---|---:|---:|---:|",
            ]
            for d, z in r["inference"].items():
                rows.append(
                    f'| {d} | {z["iid"]["se"]:.4f} | {z["day"]["se"]:.4f} | {z["week"]["se"]:.4f} |'
                )
            rows += [
                "",
                "Treating rows as independent produces much narrower uncertainty. Cluster methods differ materially; neither six weekly blocks nor reused matched controls justify strong absence-of-edge claims. "
                + source("matched_control.py", "week = np.array"),
            ]
        elif name == "cost_assumptions":
            rows += [
                "| Assumed round-trip cost | Up excess R | Down excess R |",
                "|---|---:|---:|",
            ]
            for cost, z in r.items():
                rows.append(
                    f'| {float(cost)*100:.1f}% | {fmt(z["exact"]["up"]["net_R_excess"])} | {fmt(z["exact"]["down"]["net_R_excess"])} |'
                )
            rows += [
                "",
                "No positive edge is established. R-normalized excess shifts because treated/control ATRs differ. A flat percentage fee cancels an identically charged raw-percentage excess, not necessarily an ATR-normalized excess. This does not model liquidity, funding, fills or account fee tiers. "
                + source("recon.py", "cost_atr ="),
            ]
        elif name == "multiple_comparisons":
            candidate = next(
                v for v in r["cells"] if v["name"] == "confidence 95-101 / down"
            )
            rows += [
                f'{r["family_size"]} label/direction/confidence cells, {r["weeks"]} observed ISO weeks, and {r["sign_patterns"]} joint sign patterns. None has familywise p below 0.05 in this exploratory calculation. The 95+ down cell has n={candidate["n"]:,}, excess {fmt(candidate["effect_R"])} R and familywise p={candidate["familywise_max_score_p"]:.4f}.',
                "",
                "The sign-flip calculation assumes symmetric independent week-level scores; those assumptions are not established. The tested family omits undocumented earlier searches. A high cluster score is not a calibrated normal z statistic with six blocks. No threshold earns deployment. "
                + source("matched_control.py", "for lo, hi in ((50, 60)"),
            ]
        elif name == "control_signal_contamination":
            rows += [
                "| Controls / direction | Matched | Excess R | Week interval |",
                "|---|---:|---:|---|",
            ]
            for policy in ("all_hour_controls", "non_signal_hour_controls"):
                for d, z in r[policy].items():
                    rows.append(
                        f'| {policy} / {d} | {z["n"]:,} | {fmt(z["net_R_excess"])} | {ci(z)} |'
                    )
            rows += [
                "",
                "The source baseline includes hours with other signals. Excluding them changes the question and increases unmatched cases; it does not by itself produce a significant positive advantage. "
                + source("recon.py", "baseline: every"),
            ]
        elif name == "market_wide_drift":
            rows += [
                "A common-cohort follow-up removes the target coin from its market benchmark and requires at least 20 other coins at the timestamp. Both contrasts use identical rows. "
                + link(market_path, 1),
                "",
                "| Condition | Coin-demeaned contrast ATR | Leave-one-out market-neutral ATR | Exploratory week interval for adjusted contrast |",
                "|---|---:|---:|---|",
            ]
            for i, (condition, z) in enumerate(market.items(), 1):
                a = z["coin_demeaned_same_cohort"]
                b = z["leave_one_coin_out_market_neutral"]
                interval = "[" + ", ".join(fmt(x) for x in b["week_bootstrap_95"]) + "]"
                rows.append(
                    f'| {condition} {link(market_path,i)} | {fmt(a["effect_ATR"])} | {fmt(b["effect_ATR"])} | {interval} |'
                )
            rows += [
                "",
                "The earlier “volume gate predicts weaker returns” and “high risk status points the wrong way” interpretations are not robust to market adjustment. The top-band contrast also shrinks. This benchmark is an ex-post outcome comparison, not a point-in-time feature or executable hedge; beta and universe coverage remain limitations. "
                + source("thr_candle2.py", "xr, xm = demean"),
            ]
        elif name == "survivorship_and_coverage":
            rows += [
                "| Observed cohort | Coins | Rows | Top-band contrast ATR | Down-volume contrast ATR |",
                "|---|---:|---:|---:|---:|",
            ]
            for cohort, z in r["cohorts"].items():
                rows.append(
                    f'| {cohort} | {z["coins"]} | {z["rows"]:,} | {fmt(z["effects"]["top_85_vs_rest"])} | {fmt(z["effects"]["down_volume_1.5"])} |'
                )
            rows += [
                "",
                "True survivorship correction is UNTESTABLE from these snapshots: historical listing membership, omitted/delisted instruments and their outcomes are missing. The coverage screen is itself hindsight-selected and is only a sensitivity check. No conclusion for the whole historical Coinbase universe is justified. The reconstruction baseline additionally keeps only products with usable signals. "
                + source("recon.py", "sigprods ="),
            ]
        elif name == "lookahead_feature_poison_and_horizon":
            rows += [
                f'{r["real_signal_samples"]} real four-coin samples: {r["features_changed_by_future_poison"]} ATR/extension/BTC feature changes after future-price poisoning. The source forward endpoint ranges from {r["actual_forward_hours_min_max"][0]:.4f} to {r["actual_forward_hours_min_max"][1]:.4f} hours, versus {r["baseline_forward_hours"]} hours for boundary baseline entries. Initial omitted minutes range from {r["ignored_initial_minutes_min_max"][0]:.2f} to {r["ignored_initial_minutes_min_max"][1]:.2f}.',
                "",
                "No tested feature leak was found, which is not proof that all archived snapshots were point-in-time. The source r4/r12/r24 indices correspond to 3/11/23 forward bars at an exact boundary. Sell-side replay timestamps label the feature candle start although its close is known an hour later; that is safe only if downstream joins honor actual feature availability. Horizon mismatch and omitted early path remain real comparability limitations; this test does not regrade the entire dataset. "
                + source("recon.py", "tb = -(-entry_ts")
                + " "
                + source("recon.py", "float(ret[2])")
                + " "
                + source("thr_candle.py", "out.append((prod, int(ts[i])"),
            ]
        elif name == "evidence_interval_estimand":
            rows += [
                "| Label / direction | Matched n | Signal-weighted R | Equal-week R | Consistent weighted ISO-week interval |",
                "|---|---:|---:|---:|---|",
            ]
            for z in r:
                interval = (
                    "["
                    + ", ".join(
                        fmt(v)
                        for v in z["consistent_weighted_week_bootstrap"][
                            "percentile_95"
                        ]
                    )
                    + "]"
                )
                rows.append(
                    f'| {z["label"]} / {z["direction"]} | {z["n"]:,} | {fmt(z["signal_weighted_mean_R"])} | {fmt(z["equal_weight_week_mean_R"])} | {interval} |'
                )
            rows += [
                "",
                "The source centers an interval on the signal-weighted mean but computes its SE from equally weighted weekly means, discarding thin weeks only for SE. It also groups epoch-based Thursday weeks while describing calendar-week uncertainty. A +0.10 R practical advantage is still inside several exploratory intervals; these data do not uniformly rule it out. The useful-effect margin was not verified as preregistered. "
                + source("evidence_block.py", "wk =")
                + " "
                + source("evidence_block.py", "se =")
                + " "
                + source("matched_control.py", "week = np.array"),
            ]
        elif name == "ambiguous_first_touch":
            rows += [
                "| Direction | Signal ambiguous | Control ambiguous | Ordering-only excess R bounds |",
                "|---|---:|---:|---|",
            ]
            for d, z in r.items():
                rows.append(
                    f'| {d} | {z["signal_ambiguous_fraction"]:.2%} | {z["control_ambiguous_fraction"]:.2%} | [{fmt(z["ordering_only_excess_R_bounds"][0])}, {fmt(z["ordering_only_excess_R_bounds"][1])}] |'
                )
            rows += [
                "",
                "Intrabar ordering alone does not explain a positive up-signal advantage here. These are worst-case ordering bounds, not sampling intervals or actual stop-fill bounds. The original charges every ambiguous candle as stop-first. "
                + source("recon.py", "elif tS < 99:"),
            ]
        elif name == "BH_step_up_illustration":
            rows += [
                f'ILLUSTRATIVE ONLY: p-values {r["p_values"]} produce source flags {r["source_flags"]}, versus step-up flags {r["correct_step_up_flags"]}. These are synthetic p-values, not observations.',
                "",
                "This demonstrates an implementation problem in the source BH closure. It does not establish that any actual empirical result would change significance, and the example is conservative for its first test. "
                + source("ctrl_tests.py", "bh ="),
            ]
        rows += [
            "",
            "Result evidence: " + reference + ".",
            "Conclusion impact: "
            + record["effect_on_conclusion"]
            + " "
            + reference
            + ".",
            "",
        ]
    rows += [
        "## Remaining limits",
        "",
        "No historical membership correction, fully point-in-time live order-flow reconstruction, exact intraminute execution, or complete historical model-search accounting is possible from the supplied copies. The audit did not fetch production, rebuild the owner’s active archive, or repair any original script. These are explicit evidence gaps, not zero-valued results. "
        + link(RUN / "copy_manifest.json", 1)
        + " "
        + code("def main("),
        "",
        "Reproduce internally from the frozen copies: `PYTHONDONTWRITEBYTECODE=1 python research/redteam_20261018/audit_experiments.py NEW_RESULT_DIRECTORY`, then run this report builder. Existing output directories are refused. Requires Python and NumPy. The frozen source files contain their original owner-path I/O and are reference material only; the adapted runner opens only the copied inputs. "
        + code("def ro("),
    ]
    (REPORTS / "RED_TEAM_REPORT.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )


def sample(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_public():
    initial = RUN / "public_samples_initial"
    history = RUN / "public_samples_history"
    archives = RUN / "public_samples_archives"
    api = "https://www.okx.com/docs-v5/en/"
    cbbook = "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book"
    cbrate = "https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits"
    cbterms = "https://www.coinbase.com/legal/market_data"
    okterms = "https://www.okx.com/help/okx-api-agreement"
    sdk = "https://github.com/okxapi/python-okx/blob/master/okx/TradingData.py#L44"
    rows = [
        "# Internal public-data prototype — 2026-10-18",
        "",
        "Only tiny unauthenticated GET probes and bounded archive samples were made. No sign-up, key, account, private endpoint, production request, or region bypass was used. Standard/history request-start logs enforce >=1 second spacing; archive requests use the same scheduler. "
        + link(ROOT / "public_source_fetcher.py", 1)
        + " "
        + link(initial / "requests.jsonl", 1)
        + " "
        + link(history / "requests.jsonl", 1),
        "",
        "Verified intersection: BTC and SOL have Coinbase USD product metadata and OKX derivative samples. This tests two assets, not full Coinbase-asset coverage. "
        + link(initial / "coinbase_BTC_listing.json", 1)
        + " "
        + link(initial / "coinbase_SOL_listing.json", 1)
        + " "
        + link(initial / "okx_SOL_funding_recent.json", 1),
        "",
        "| Data type | What was actually saved | History demonstrated | Documentation / limits |",
        "|---|---|---|---|",
        f'| Coinbase depth | Two native Level-2 snapshots each for BTC-USD and SOL-USD; aggregated price, size, order count, sequence/time. {link(initial/"coinbase_BTC_depth_1.json",1)} {link(initial/"coinbase_SOL_depth_1.json",1)} | Snapshot route has no documented historical time filter. Historical Coinbase depth via another service remains UNVERIFIED. | [Book schema]({cbbook}); [public rate limit]({cbrate}): 10/s per IP, burst 15. |',
        f'| OKX historical depth for a Coinbase-listed asset | Four decoded BTC-USDT 400-level book messages from a bounded archive prefix; schema includes instrument, action, timestamp, asks/bids. {link(archives/"okx_BTC_depth_2025_sample.json",1)} | Actual decoded sample is from October 2025, at least a year back. Exact earliest date and continuous instrument coverage UNVERIFIED; no full archive was downloaded or CRC-validated. | [Historical market data]({api}#public-data-rest-api-get-historical-market-data): module 4; index 5 requests/2s per IP. Data backfill varies; books generally T+3. |',
        f'| OKX funding | Native settlement-rate history for BTC/SOL, plus three funding rows from an October 2025 monthly ZIP. {link(initial/"okx_BTC_funding_recent.json",1)} {link(initial/"okx_SOL_funding_recent.json",1)} {link(archives/"okx_BTC_funding_2025_sample.json",1)} | Rolling API returned a 90-day probe, none at a year; archived monthly data supplied actual year-old rows. {link(initial / "okx_BTC_funding_90d.json", 1)} {link(initial / "okx_BTC_funding_365d.json", 1)} Exact earliest archive date/continuity UNVERIFIED. | [Funding history]({api}#public-data-rest-api-get-funding-rate-history): up to 3 months, max 400/page, 10 requests/2s per IP+instrument. [Archive index]({api}#public-data-rest-api-get-historical-market-data) is a separate route. |',
        f'| OKX open interest | Current BTC/SOL contract/coin/USD fields plus historical arrays and timestamps. {link(initial/"okx_BTC_oi_current.json",1)} {link(initial/"okx_SOL_oi_recent.json",1)} | Hourly: data at 59 days, empty at 61. 4H: data at 90 days. Daily UTC: two rows a year back. {link(history/"okx_BTC_oi_59d_1H.json",1)} {link(history/"okx_BTC_oi_61d_1H.json",1)} {link(history/"okx_BTC_oi_90d_4H.json",1)} {link(history/"okx_BTC_oi_365d_1Dutc.json",1)} | [OI history]({api}#trading-statistics-rest-api-get-contract-open-interest-history) describes latest 1,440 entries, max 100/page; 10 requests/2s per IP+instrument. [Official SDK]({sdk}). Current OI: 20 requests/2s. Earliest documented floors and all-asset availability not independently verified. |',
        f'| Bybit funding/OI candidate | First funding request returned country-block HTTP 403; remaining host requests stopped. {link(initial/"bybit_BTC_funding_recent.json",1)} | No live history or permission-to-use verified from this environment. Do not bypass the restriction. | [OI endpoint](https://bybit-exchange.github.io/docs/v5/market/open-interest): 5min through 1d, max 200/page; [IP limit](https://bybit-exchange.github.io/docs/v5/rate-limit): default 600/5s. Docs describe capability, not demonstrated local availability. |',
        "",
        "These sources measure different venues and quotes: Coinbase USD spot depth is not OKX USDT spot depth or perpetual positioning. Funding is a rate at its settlement interval, not an annual return. OI is venue-specific positioning, not total market exposure. History-array instrument scaling and complete symbol mapping remain UNVERIFIED; preserve raw unit fields until instrument specifications are reconciled. "
        + link(initial / "okx_BTC_oi_current.json", 1)
        + f" [Schemas]({api}).",
        "",
        "## Terms and deployment boundary",
        "",
        f"Coinbase’s [Market Data Terms]({cbterms}) sections 2 and 3 restrict use and outside-organization redistribution of data/derived works. Section 3(5) also explicitly restricts use involving AI/ML and other automated systems. This prototype is not a determination that BHABIT’s intended automated or user-facing use is permitted. Applicable contractual consent remains UNVERIFIED.",
        f"OKX’s [API Agreement]({okterms}) section 9.4 applies to unauthenticated users too. It restricts third-party redistribution, competing data/analytics products, and specified commercial/third-party AI use. Public accessibility does not establish a reusable or redistributable license. This was a personal research availability test, not permission to publish a dashboard feed.",
        "Raw public samples and numerical analysis reports are kept local under `.runtime/redteam_20261018/`, excluded from Git. Only copied/adapted code is intended for the branch. Third-party display, commercial use, full historical continuity and exact oldest dates are UNVERIFIED. "
        + link(ROOT / "public_source_fetcher.py", 1),
        "",
        "## Commands",
        "",
        "`python research/redteam_20261018/public_source_fetcher.py standard` — listing/depth/funding/OI handful.",
        "`python research/redteam_20261018/public_source_fetcher.py history` — bounded retention and public archive-index probes.",
        "`python research/redteam_20261018/public_source_fetcher.py archive_samples` — tiny samples from returned year-old archive URLs; no bulk pull.",
        "Each mode refuses an existing output directory. Archive downloads request a bounded byte range and parse only a few rows. A partial archive sample proves those rows were retrievable; it does not prove full-file integrity or uninterrupted history. "
        + link(ROOT / "public_source_fetcher.py", 1),
    ]
    (REPORTS / "PUBLIC_DATA_REPORT.md").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    REPORTS.mkdir(parents=True, exist_ok=False)
    write_audit()
    write_public()
    print(str(REPORTS / "RED_TEAM_REPORT.md"))
    print(str(REPORTS / "PUBLIC_DATA_REPORT.md"))
