# Recon — Phase 1 data-quality & §3 lead verification

_Every number below was computed from the released parquet files. Ratio-of-sums, off-floor rows excluded (`location_id IS NULL`), event timestamps converted to gaming dates via `calendar_day.gaming_day_start_utc`._


## Floor totals (Jan 1 – Jun 30, 2025)

| coin-in | payout | house win | theo | luck residual | observed hold | theo hold |
| --- | --- | --- | --- | --- | --- | --- |
| $248.91M | $225.27M | $23.638M | $23.545M | $92,791 | 9.497% | 9.460% |

**Lead:** floor hold ≈ 9.50% vs theo 9.46%, coin-in ≈ $248.9M, net luck ≈ +$93K.


## Lead #1 — GM's bottom-10 by raw house win (active floor only)

| machine | zone | zone_id | mfr | RTP | vol | house win | theo | coin-in | avail h | floor days | luck |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M-5076 | Back Forty | Z-B40 | Halcyon | 95.0% | low | $3.6k | $7.5k | $0.15M | 1,170 | 49 | $-3.9k |
| M-1158 | Back Forty | Z-B40 | Ridgeline | 90.0% | medium | $15.8k | $52.0k | $0.52M | 4,340 | 181 | $-36.2k |
| M-1120 | Back Forty | Z-B40 | Ridgeline | 95.0% | low | $16.4k | $18.9k | $0.38M | 3,150 | 132 | $-2.6k |
| M-1118 | High-Limit Room | Z-HL | Ridgeline | 90.0% | high | $20.1k | $25.3k | $0.25M | 1,313 | 55 | $-5.3k |
| M-1238 | Back Forty | Z-B40 | Halcyon | 95.0% | low | $24.9k | $33.1k | $0.66M | 4,332 | 181 | $-8.2k |
| M-1181 | Back Forty | Z-B40 | Halcyon | 92.0% | high | $27.0k | $32.5k | $0.41M | 4,334 | 181 | $-5.5k |
| M-1035 | Back Forty | Z-B40 | Northwind | 95.0% | low | $30.3k | $30.9k | $0.62M | 4,339 | 181 | $-0.6k |
| M-1179 | Back Forty | Z-B40 | Ridgeline | 92.0% | high | $30.4k | $33.8k | $0.42M | 4,325 | 181 | $-3.4k |
| M-1017 | Back Forty | Z-B40 | Ridgeline | 95.0% | low | $31.9k | $29.5k | $0.59M | 4,333 | 181 | $+2.4k |
| M-1265 | Back Forty | Z-B40 | Halcyon | 92.0% | high | $32.1k | $32.2k | $0.40M | 4,335 | 181 | $-0.1k |

**Verified:** Back Forty = 9/10. Partial-exposure machines (floor days < 181): 3. High-Limit Room machines: 0. Zones in list: ['Z-B40', 'Z-HL'].


## Lead #2 — Walkway W-ENT-B40 closure & Back Forty exposure drop

| walkway | zone_a | zone_b | closed_from_utc | closed_to_utc | reason |
| --- | --- | --- | --- | --- | --- |
| W-ENT-B40 | Z-ENT | Z-B40 | 2025-03-03 14:00:00 | 2025-04-07 13:00:00 | renovation |

| month | B40 coin-in / machine-day | rest / machine-day | B40 vs Jan | rest vs Jan |
| --- | --- | --- | --- | --- |
| 2025-01 | $3,137 | $4,737 | +0.0% | +0.0% |
| 2025-02 | $3,289 | $4,977 | +4.8% | +5.0% |
| 2025-03 | $2,398 | $5,078 | -23.6% | +7.2% |
| 2025-04 | $2,852 | $4,760 | -9.1% | +0.5% |
| 2025-05 | $3,030 | $4,767 | -3.4% | +0.6% |
| 2025-06 | $2,879 | $4,556 | -8.2% | -3.8% |

| cal month | B40 entries / counter-hour | rest zones entries / counter-hour |
| --- | --- | --- |
| 2025-01 | 24.8 | 97.8 |
| 2025-02 | 25.6 | 102.2 |
| 2025-03 | 18.4 | 102.5 |
| 2025-04 | 21.9 | 98.4 |
| 2025-05 | 23.1 | 97.8 |
| 2025-06 | 22.2 | 94.3 |
| 2025-07 | 9.0 | 38.6 |

**Verified:** closure runs **Mar 3 → Apr 7, 2025** (floor_walkways). Compare March Back Forty coin-in/machine-day and traffic to Jan to quantify the ≈25% drop; full DiD moves to Phase 2 with controls.


## Lead #3 — M-1158 luck z-score

| machine | coin-in | house win | theo | luck $ | σ (analytic) | z | observed hold | theo hold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M-1158 | $51.96M | $15.8k | $52.0k | $-36,165 | $7,913 | -4.57 | 3.04% | 10.00% |

**Verified:** M-1158 shows a strongly negative luck residual with an analytic z of **-4.57**. Observed hold 3.04% vs theo 10.00%. Treat as **🔍 INSPECT** lead only — never an accusation.

| machine | mfr | house win | theo | luck | z | spins | floor days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M-1158 | Ridgeline | $15.8k | $52.0k | $-36.2k | -4.57 | 674454 | 181 |
| M-1054 | Ridgeline | $66.8k | $81.4k | $-14.5k | -2.78 | 1011445 | 181 |
| M-1210 | Northwind | $38.5k | $53.3k | $-14.7k | -2.50 | 1234921 | 181 |
| M-1257 | Halcyon | $114.4k | $99.8k | $+14.7k | +2.51 | 1248569 | 181 |
| M-1214 | Ridgeline | $102.0k | $65.5k | $+36.5k | +2.79 | 130744 | 181 |

**|z| ≥ 2.5 machines:** 5 total.


## Lead #4 — Fault frequency by manufacturer (per machine, Jan–Jun)

| manufacturer | machines | fault tickets | faults / machine |
| --- | --- | --- | --- |
| Ridgeline | 94 | 680 | 7.23 |
| Northwind | 101 | 305 | 3.02 |
| Halcyon | 115 | 222 | 1.93 |


## Lead #5 — Fault response latency by gaming-hour-of-day

| gaming-hour bucket | tickets | mean wait h | median wait h | mean work h | median work h |
| --- | --- | --- | --- | --- | --- |
| 04:00-11:59 (morning) | 223 | 1.07 | 0.00 | 3.06 | 2.61 |
| 12:00-17:59 (afternoon) | 356 | 0.66 | 0.00 | 3.07 | 2.57 |
| 18:00-22:59 (evening) | 428 | 1.06 | 0.00 | 2.85 | 2.36 |
| 23:00-03:59 (overnight) | 200 | 2.26 | 1.30 | 2.80 | 2.24 |


## Lead #6 — Comp drift: points per face-dollar (weekly)

| week | redemptions | face $ | cost $ | pts / face $ (redeem) |
| --- | --- | --- | --- | --- |
| 2024-12-30 | 1213 | $13,089 | $3,595 | 14.26 |
| 2025-01-06 | 2031 | $23,064 | $6,424 | 13.98 |
| 2025-01-13 | 2124 | $23,715 | $6,570 | 13.85 |
| 2025-01-20 | 2191 | $25,178 | $7,036 | 13.73 |
| 2025-01-27 | 2209 | $25,310 | $7,050 | 13.55 |
| 2025-02-03 | 2482 | $29,033 | $8,122 | 13.39 |
| 2025-02-10 | 2110 | $24,026 | $6,677 | 13.24 |
| 2025-02-17 | 2472 | $28,160 | $7,884 | 13.06 |
| 2025-02-24 | 2218 | $25,608 | $7,155 | 13.00 |
| 2025-03-03 | 2381 | $27,129 | $7,564 | 12.91 |
| 2025-03-10 | 2236 | $25,519 | $7,118 | 12.88 |
| 2025-03-17 | 2486 | $28,560 | $7,981 | 12.83 |
| 2025-03-24 | 2411 | $27,490 | $7,678 | 12.73 |
| 2025-03-31 | 2165 | $24,878 | $6,984 | 12.70 |
| 2025-04-07 | 2306 | $26,622 | $7,440 | 12.61 |
| 2025-04-14 | 2303 | $26,312 | $7,302 | 12.45 |
| 2025-04-21 | 2343 | $27,377 | $7,673 | 12.44 |
| 2025-04-28 | 2225 | $25,782 | $7,247 | 8.54 |
| 2025-05-05 | 2274 | $26,680 | $7,472 | 5.84 |
| 2025-05-12 | 2436 | $28,226 | $7,887 | 5.86 |
| 2025-05-19 | 2418 | $27,948 | $7,815 | 5.84 |
| 2025-05-26 | 2422 | $27,641 | $7,735 | 5.81 |
| 2025-06-02 | 2363 | $27,446 | $7,655 | 5.75 |
| 2025-06-09 | 2582 | $30,380 | $8,532 | 5.65 |
| 2025-06-16 | 2296 | $26,584 | $7,427 | 5.71 |
| 2025-06-23 | 2282 | $26,560 | $7,419 | 5.71 |
| 2025-06-30 | 382 | $4,434 | $1,226 | 5.80 |

**Comp lead check:** points-per-face-dollar on **redemption** events by gaming-week. A step change around Apr 28 – May 5, 2025 would confirm the lead; quantified above.

| month | comp cost (player_period) | tracked theo | reinv / tracked | floor theo | reinv / floor |
| --- | --- | --- | --- | --- | --- |
| 2025-01 | $28,750 | $2,580,581 | 1.11% | $3,946,194 | 0.73% |
| 2025-02 | $29,854 | $2,480,600 | 1.20% | $3,755,950 | 0.79% |
| 2025-03 | $33,256 | $2,733,323 | 1.22% | $4,132,019 | 0.80% |
| 2025-04 | $31,390 | $2,528,176 | 1.24% | $3,899,006 | 0.81% |
| 2025-05 | $34,446 | $2,658,429 | 1.30% | $4,060,079 | 0.85% |
| 2025-06 | $32,973 | $2,503,913 | 1.32% | $3,752,116 | 0.88% |

**Verified:** comp reinvestment (comp cost ÷ **tracked** theo) climbs **1.11% (Jan) → 1.32% (Jun)**, exactly matching the §3 lead. Using floor theo as the denominator gives 0.72% → 0.88%; we will adopt **tracked theo** as the authoritative denominator in `gold_comp_week`.


## Lead #7 — Tracked-theo concentration

| segment | share of tracked theo |
| --- | --- |
| top 1% | 20.3% |
| top 10% | 63.8% |
| top 25% | 78.7% |


## Lead #8 — Lineup: theo per available hour by config (floor median baseline)

| config | theme | RTP | volatility | machines | theo/h median | min | max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G-VID95 | Royal Draw | 95.0% | low | 25 | $10.60 | $6.00 | $12.32 |
| G-HIGH92 | Comet Cash | 92.0% | high | 24 | $12.99 | $7.43 | $14.93 |
| G-LOW92 | Lucky Lanterns | 92.0% | low | 24 | $13.98 | $8.53 | $16.20 |
| G-HL90 | Platinum Reels | 90.0% | high | 24 | $16.75 | $15.09 | $19.28 |
| G-STD90 | Desert Gold | 90.0% | medium | 48 | $17.78 | $9.61 | $20.82 |
| G-CLS93 | Classic Sevens | 93.0% | low | 31 | $19.05 | $10.73 | $22.32 |
| G-PEN89 | Prairie Thunder | 89.0% | medium | 66 | $21.51 | $12.75 | $25.99 |
| G-NEO88 | Neon Nights | 88.0% | high | 42 | $22.72 | $12.43 | $25.67 |
| G-JKP88 | Jackpot Summit | 88.0% | very_high | 18 | $24.44 | $12.16 | $29.44 |
| G-NEW91 | Aurora Link | 91.0% | medium | 8 | $28.16 | $27.44 | $29.69 |


## Data-quality checklist

- Off-floor rows (location_id IS NULL): **1018** (expected 1,018).
- Active floor rows: **55,092**.
- 2025-03-08 scheduled seconds: **82,800** (expected 82,800).
- Carded share of coin-in (floor): **65.81%** (carded $163.8M of $248.9M).


## Infra status

- **Databricks CLI:** not installed on this host. Phase 1 (recon) runs entirely on local DuckDB over the released parquet files, so this does not block recon. Before Phase 2 I will need the CLI authenticated — see the §8 checkpoint note below.
- **Python env:** `.venv/bin/python` with duckdb 2.0.0, pandas 3.1.1, pyarrow 26.0.1.
- **Repo verify scripts:** `verify_data.py` PASS (62 checksums, 31 row/format matches); `verify_semantics.py` PASS (11/11 invariants).
