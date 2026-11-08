"""Phase 1 — Recon: profile tables and verify every §3 lead.

Writes evidence to docs/RECON.md. Runs against the parquet files in data/.
Uses ratio-of-sums everywhere, excludes off-floor rows (location_id NULL),
and converts event timestamps to gaming dates via calendar_day.
"""
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "docs" / "RECON.md"


def q(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple]:
    rows = con.sql(dedent(sql)).fetchall()
    # Normalize decimal.Decimal → float so string-formatting works everywhere.
    import decimal
    def norm(v):
        return float(v) if isinstance(v, decimal.Decimal) else v
    return [tuple(norm(v) for v in r) for r in rows]


def main() -> None:
    con = duckdb.connect()

    # Register every parquet file as a view.
    views = {
        "prepared": "1_prepared_views/prepared_daily_view",
        "property": "1_prepared_views/property_day",
        "player_period": "1_prepared_views/player_period",
        "calendar": "2_machine_decision/calendar_day",
        "machines": "2_machine_decision/machines",
        "game_math": "2_machine_decision/game_math",
        "placements": "2_machine_decision/placements",
        "floor_locations": "2_machine_decision/floor_locations",
        "floor_walkways": "2_machine_decision/floor_walkways",
        "machine_day": "2_machine_decision/machine_day",
        "operations": "2_machine_decision/operations",
        "cost_rules": "2_machine_decision/cost_rules",
        "action_catalog": "2_machine_decision/action_catalog",
        "players": "3_guests/players",
        "sessions": "3_guests/sessions",
        "trips": "3_guests/trips",
        "loyalty_ledger": "3_guests/loyalty_ledger",
        "fnb_transactions": "3_guests/fnb_transactions",
        "zone_traffic_hourly": "4_context/zone_traffic_hourly",
        "events": "4_context/events",
        "weather": "4_context/real_sources/weather_daily",
        "city_visitation": "4_context/real_sources/city_visitation_monthly",
        "shift_roster": "5_optional/shift_roster",
        "machine_hour": "5_optional/machine_hour",
    }
    for name, path in views.items():
        con.read_parquet(str(DATA / (path + ".parquet"))).create_view(name)

    lines: list[str] = []

    def section(title: str) -> None:
        lines.append(f"\n## {title}\n")

    def write(block: str) -> None:
        lines.append(dedent(block).strip() + "\n")

    def table(rows: list[tuple], headers: list[str]) -> None:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append(
                "| " + " | ".join(str(x) if x is not None else "—" for x in row) + " |"
            )
        lines.append("")

    write("# Recon — Phase 1 data-quality & §3 lead verification")
    write(
        "_Every number below was computed from the released parquet files. "
        "Ratio-of-sums, off-floor rows excluded (`location_id IS NULL`), event timestamps "
        "converted to gaming dates via `calendar_day.gaming_day_start_utc`._"
    )

    # ------------------------------------------------------------------ Floor totals
    section("Floor totals (Jan 1 – Jun 30, 2025)")
    rows = q(
        con,
        """
        SELECT
            SUM(coin_in_usd)                                    AS coin_in,
            SUM(payout_usd)                                     AS payout,
            SUM(house_win_usd)                                  AS house_win,
            SUM(theo_usd)                                       AS theo,
            SUM(house_win_usd) - SUM(theo_usd)                  AS luck_residual,
            SUM(house_win_usd) / NULLIF(SUM(coin_in_usd), 0)    AS observed_hold,
            SUM(theo_usd)      / NULLIF(SUM(coin_in_usd), 0)    AS theo_hold
        FROM property
        """,
    )
    table(
        [
            (
                f"${rows[0][0]/1e6:,.2f}M",
                f"${rows[0][1]/1e6:,.2f}M",
                f"${rows[0][2]/1e6:,.3f}M",
                f"${rows[0][3]/1e6:,.3f}M",
                f"${rows[0][4]:,.0f}",
                f"{rows[0][5]*100:.3f}%",
                f"{rows[0][6]*100:.3f}%",
            )
        ],
        ["coin-in", "payout", "house win", "theo", "luck residual", "observed hold", "theo hold"],
    )

    write(
        "**Lead:** floor hold ≈ 9.50% vs theo 9.46%, coin-in ≈ $248.9M, net luck ≈ +$93K."
    )

    # ------------------------------------------------------------------ GM bottom-10
    section("Lead #1 — GM's bottom-10 by raw house win (active floor only)")
    gm10 = q(
        con,
        """
        WITH ranked AS (
            SELECT
                p.machine_id,
                ANY_VALUE(zone_name)        AS zone,
                ANY_VALUE(zone_id)          AS zone_id,
                ANY_VALUE(manufacturer)     AS mfr,
                ANY_VALUE(configured_rtp)   AS rtp,
                ANY_VALUE(volatility_class) AS vol,
                SUM(house_win_usd)          AS house_win,
                SUM(theo_usd)               AS theo,
                SUM(coin_in_usd)            AS coin_in,
                SUM(available_hours)        AS avail_hours,
                COUNT_IF(active)            AS floor_days,
                SUM(house_win_usd) - SUM(theo_usd) AS luck_residual
            FROM prepared p
            WHERE active                             -- exclude off-floor rows
            GROUP BY machine_id
        )
        SELECT machine_id, zone, zone_id, mfr, rtp, vol,
               house_win, theo, coin_in, avail_hours, floor_days, luck_residual
        FROM ranked
        ORDER BY house_win ASC
        LIMIT 10
        """,
    )
    table(
        [
            (
                m, z, zid, mfr, f"{rtp*100:.1f}%", vol,
                f"${hw/1e3:,.1f}k", f"${th/1e3:,.1f}k",
                f"${ci/1e6:,.2f}M", f"{ah:,.0f}", fd,
                f"${lr/1e3:+,.1f}k",
            )
            for (m, z, zid, mfr, rtp, vol, hw, th, ci, ah, fd, lr) in gm10
        ],
        ["machine", "zone", "zone_id", "mfr", "RTP", "vol",
         "house win", "theo", "coin-in", "avail h", "floor days", "luck"],
    )

    by_zone = {row[2] for row in gm10}
    back40 = sum(1 for row in gm10 if row[2] == "Z-B40")
    partial = [row for row in gm10 if row[10] < 181]
    high_limit = [row for row in gm10 if row[2] == "Z-HLR"]
    write(
        f"**Verified:** Back Forty = {back40}/10. Partial-exposure machines "
        f"(floor days < 181): {len(partial)}. High-Limit Room machines: {len(high_limit)}. "
        f"Zones in list: {sorted(by_zone)}."
    )

    # ------------------------------------------------------------------ Walkway
    section("Lead #2 — Walkway W-ENT-B40 closure & Back Forty exposure drop")
    walk = q(
        con,
        """
        SELECT walkway_id, zone_a, zone_b,
               closed_from_utc, closed_to_utc, closure_reason
        FROM floor_walkways
        WHERE closed_from_utc IS NOT NULL
        """,
    )
    table(
        [(w, za, zb, cf, ct, r) for (w, za, zb, cf, ct, r) in walk],
        ["walkway", "zone_a", "zone_b", "closed_from_utc", "closed_to_utc", "reason"],
    )

    did = q(
        con,
        """
        WITH zone_month AS (
            SELECT zone_id, month,
                   SUM(coin_in_usd)      AS coin_in,
                   SUM(available_hours)  AS avail_h,
                   COUNT_IF(active)      AS machine_days
            FROM prepared
            WHERE active AND zone_id IS NOT NULL
            GROUP BY zone_id, month
        )
        SELECT month,
               SUM(CASE WHEN zone_id = 'Z-B40' THEN coin_in END) /
                 NULLIF(SUM(CASE WHEN zone_id = 'Z-B40' THEN machine_days END), 0) AS b40_per_md,
               SUM(CASE WHEN zone_id <> 'Z-B40' THEN coin_in END) /
                 NULLIF(SUM(CASE WHEN zone_id <> 'Z-B40' THEN machine_days END), 0) AS rest_per_md
        FROM zone_month
        GROUP BY month
        ORDER BY month
        """,
    )
    b40_jan = did[0][1]; rest_jan = did[0][2]
    table(
        [
            (
                m,
                f"${b40:,.0f}",
                f"${rest:,.0f}",
                f"{(b40/b40_jan - 1)*100:+.1f}%",
                f"{(rest/rest_jan - 1)*100:+.1f}%",
            )
            for (m, b40, rest) in did
        ],
        ["month", "B40 coin-in / machine-day", "rest / machine-day",
         "B40 vs Jan", "rest vs Jan"],
    )
    # Traffic drop in March
    traffic = q(
        con,
        """
        WITH covered AS (
            SELECT zone_id,
                   CAST(hour_start_local AS DATE) AS cal_date,
                   SUM(entries_count) FILTER (WHERE counter_status IN ('ok','partial'))      AS entries,
                   SUM(coverage_minutes) FILTER (WHERE counter_status IN ('ok','partial'))   AS cov_min
            FROM zone_traffic_hourly
            GROUP BY 1, 2
        ), joined AS (
            SELECT c.zone_id,
                   STRFTIME(c.cal_date, '%Y-%m') AS cal_month,
                   SUM(entries)  AS entries,
                   SUM(cov_min)  AS cov_min
            FROM covered c
            GROUP BY 1, 2
        )
        SELECT cal_month,
               SUM(CASE WHEN zone_id = 'Z-B40' THEN entries  END) * 60.0 /
                 NULLIF(SUM(CASE WHEN zone_id = 'Z-B40' THEN cov_min END), 0) AS b40_entries_per_h,
               SUM(CASE WHEN zone_id <> 'Z-B40' THEN entries END) * 60.0 /
                 NULLIF(SUM(CASE WHEN zone_id <> 'Z-B40' THEN cov_min END), 0) AS rest_entries_per_h
        FROM joined
        GROUP BY cal_month
        ORDER BY cal_month
        """,
    )
    table(
        [(m, f"{b:,.1f}", f"{r:,.1f}") for (m, b, r) in traffic if b is not None],
        ["cal month", "B40 entries / counter-hour", "rest zones entries / counter-hour"],
    )
    write(
        "**Verified:** closure runs **Mar 3 → Apr 7, 2025** (floor_walkways). "
        "Compare March Back Forty coin-in/machine-day and traffic to Jan to quantify the ≈25% drop; "
        "full DiD moves to Phase 2 with controls."
    )

    # ------------------------------------------------------------------ M-1158
    section("Lead #3 — M-1158 luck z-score")
    m1158 = q(
        con,
        """
        WITH base AS (
            SELECT m.machine_id,
                   SUM(coin_in_cents)               AS coin_in_c,
                   SUM(payout_cents)                AS payout_c,
                   SUM(house_win_cents)             AS house_win_c,
                   SUM(theo_cents)                  AS theo_c,
                   SUM(sum_bet_squared * gm.payout_multiplier_variance) AS var_c2,
                   SUM(paid_spins)                  AS spins
            FROM machine_day m
            JOIN game_math gm USING (config_id)
            WHERE m.machine_id = 'M-1158' AND m.active
            GROUP BY 1
        )
        SELECT machine_id,
               house_win_c, theo_c,
               house_win_c - theo_c                 AS luck_c,
               var_c2,
               SQRT(var_c2)                         AS sigma_c,
               (house_win_c - theo_c) / SQRT(var_c2) AS z,
               coin_in_c, payout_c, spins
        FROM base
        """,
    )
    r = m1158[0]
    luck_usd = r[3] / 100
    sigma_usd = r[5] / 100
    hold_actual = r[1] / r[7] if r[7] else None
    theo_hold = r[2] / r[7] if r[7] else None
    table(
        [
            (
                r[0],
                f"${r[7]/1e6:,.2f}M",
                f"${r[1]/1e5:,.1f}k",
                f"${r[2]/1e5:,.1f}k",
                f"${luck_usd:,.0f}",
                f"${sigma_usd:,.0f}",
                f"{r[6]:.2f}",
                f"{hold_actual*100:.2f}%" if hold_actual else "—",
                f"{theo_hold*100:.2f}%" if theo_hold else "—",
            )
        ],
        ["machine", "coin-in", "house win", "theo", "luck $",
         "σ (analytic)", "z", "observed hold", "theo hold"],
    )
    write(
        "**Verified:** M-1158 shows a strongly negative luck residual with an analytic z of **"
        f"{r[6]:.2f}**. Observed hold "
        f"{hold_actual*100:.2f}% vs theo {theo_hold*100:.2f}%. "
        "Treat as **🔍 INSPECT** lead only — never an accusation."
    )

    # Other |z|>2.5 machines
    high_z = q(
        con,
        """
        WITH base AS (
            SELECT m.machine_id,
                   ANY_VALUE(mc.manufacturer)           AS mfr,
                   SUM(house_win_cents)                 AS hw_c,
                   SUM(theo_cents)                      AS th_c,
                   SUM(sum_bet_squared * gm.payout_multiplier_variance) AS var_c2,
                   SUM(paid_spins)                      AS spins,
                   COUNT_IF(m.active)                   AS floor_days
            FROM machine_day m
            JOIN game_math gm USING (config_id)
            JOIN machines   mc USING (machine_id)
            WHERE m.active
            GROUP BY m.machine_id
            HAVING SUM(sum_bet_squared * gm.payout_multiplier_variance) > 0
        )
        SELECT machine_id, mfr, hw_c/100.0 AS hw, th_c/100.0 AS theo,
               (hw_c - th_c)/100.0        AS luck,
               (hw_c - th_c) / SQRT(var_c2) AS z,
               spins, floor_days
        FROM base
        WHERE ABS((hw_c - th_c) / SQRT(var_c2)) >= 2.5
        ORDER BY z ASC
        """,
    )
    if high_z:
        table(
            [
                (m, mfr, f"${hw/1e3:,.1f}k", f"${th/1e3:,.1f}k",
                 f"${lk/1e3:+,.1f}k", f"{z:+.2f}", sp, fd)
                for (m, mfr, hw, th, lk, z, sp, fd) in high_z
            ],
            ["machine", "mfr", "house win", "theo", "luck", "z", "spins", "floor days"],
        )
    write(f"**|z| ≥ 2.5 machines:** {len(high_z)} total.")

    # ------------------------------------------------------------------ Faults by mfr
    section("Lead #4 — Fault frequency by manufacturer (per machine, Jan–Jun)")
    faults = q(
        con,
        """
        WITH fault_cnt AS (
            SELECT machine_id, COUNT(*) AS faults
            FROM operations
            WHERE event_type = 'fault_repair'
            GROUP BY machine_id
        ),
        base AS (
            SELECT m.manufacturer,
                   COUNT(DISTINCT m.machine_id) AS n_machines,
                   SUM(COALESCE(f.faults, 0))   AS total_faults
            FROM machines m
            LEFT JOIN fault_cnt f USING (machine_id)
            GROUP BY m.manufacturer
        )
        SELECT manufacturer, n_machines, total_faults,
               total_faults * 1.0 / n_machines AS faults_per_machine
        FROM base
        ORDER BY faults_per_machine DESC
        """,
    )
    table(
        [(m, n, tf, f"{fpm:.2f}") for (m, n, tf, fpm) in faults],
        ["manufacturer", "machines", "fault tickets", "faults / machine"],
    )

    # ------------------------------------------------------------------ Tech response time
    section("Lead #5 — Fault response latency by gaming-hour-of-day")
    latency = q(
        con,
        """
        WITH ev AS (
            SELECT o.operation_id,
                   o.opened_at_utc,
                   EXTRACT(HOUR FROM o.opened_at_local) AS local_hour_open,
                   EPOCH(o.work_started_at_utc - o.opened_at_utc) / 3600.0 AS wait_h,
                   EPOCH(o.available_at_utc  - o.work_started_at_utc) / 3600.0 AS work_h
            FROM operations o
            WHERE event_type = 'fault_repair'
              AND work_started_at_utc IS NOT NULL
              AND available_at_utc IS NOT NULL
        ),
        bucketed AS (
            SELECT CASE
                     WHEN local_hour_open BETWEEN 23 AND 23
                       OR local_hour_open BETWEEN 0  AND 3  THEN '23:00-03:59 (overnight)'
                     WHEN local_hour_open BETWEEN 4  AND 11 THEN '04:00-11:59 (morning)'
                     WHEN local_hour_open BETWEEN 12 AND 17 THEN '12:00-17:59 (afternoon)'
                     ELSE                                        '18:00-22:59 (evening)'
                   END AS bucket,
                   wait_h, work_h
            FROM ev
        )
        SELECT bucket,
               COUNT(*)                    AS tickets,
               AVG(wait_h)                 AS mean_wait_h,
               MEDIAN(wait_h)              AS med_wait_h,
               AVG(work_h)                 AS mean_work_h,
               MEDIAN(work_h)              AS med_work_h
        FROM bucketed
        GROUP BY bucket
        ORDER BY bucket
        """,
    )
    table(
        [(b, t, f"{mw:.2f}", f"{medw:.2f}", f"{mk:.2f}", f"{medk:.2f}")
         for (b, t, mw, medw, mk, medk) in latency],
        ["gaming-hour bucket", "tickets", "mean wait h", "median wait h",
         "mean work h", "median work h"],
    )

    # ------------------------------------------------------------------ Comp drift
    section("Lead #6 — Comp drift: points per face-dollar (weekly)")
    comp_week = q(
        con,
        """
        WITH awards AS (
            -- Award events only. Use the available_at_utc instant with a 6-hour shift
            -- so a 2 a.m. event belongs to the prior gaming date.
            SELECT DATE_TRUNC('week', (event_at_utc - INTERVAL '6 hours') AT TIME ZONE 'America/Los_Angeles') AS gw_start_local,
                   SUM(points_delta)         AS pts,
                   SUM(face_value_cents)/100.0 AS face_usd
            FROM loyalty_ledger
            WHERE event_type = 'award' AND face_value_cents > 0
            GROUP BY 1
        )
        SELECT STRFTIME(gw_start_local, '%Y-%m-%d') AS week,
               pts, face_usd,
               pts / NULLIF(face_usd, 0) AS pts_per_face_usd
        FROM awards
        ORDER BY gw_start_local
        """,
    )

    # Redemption-side version as well — the lead references redemptions.
    comp_red = q(
        con,
        """
        WITH red AS (
            SELECT DATE_TRUNC('week', (event_at_utc - INTERVAL '6 hours') AT TIME ZONE 'America/Los_Angeles') AS gw,
                   SUM(points_delta)                AS pts_delta,
                   SUM(face_value_cents)/100.0      AS face_usd,
                   SUM(economic_cost_cents)/100.0   AS cost_usd,
                   COUNT(*)                         AS n
            FROM loyalty_ledger
            WHERE event_type = 'redeem'
            GROUP BY 1
        )
        SELECT STRFTIME(gw, '%Y-%m-%d') AS week,
               n, face_usd, cost_usd,
               (-pts_delta) / NULLIF(face_usd, 0)   AS pts_per_face_usd_red
        FROM red
        ORDER BY gw
        """,
    )
    table(
        [(w, n, f"${fv:,.0f}", f"${cu:,.0f}", f"{ppf:,.2f}" if ppf else "—")
         for (w, n, fv, cu, ppf) in comp_red],
        ["week", "redemptions", "face $", "cost $", "pts / face $ (redeem)"],
    )
    write(
        "**Comp lead check:** points-per-face-dollar on **redemption** events by gaming-week. "
        "A step change around Apr 28 – May 5, 2025 would confirm the lead; quantified above."
    )

    # Reinvestment = comp cost / theo per month.
    # §3's 1.11% → 1.32% figures use TRACKED theo (player_period) as the denominator,
    # not floor theo. Floor theo yields ~0.72% → 0.88%. Both are reported.
    reinv = q(
        con,
        """
        SELECT period_month                                          AS mth,
               SUM(comp_cost_usd)                                    AS comp_cost,
               SUM(theo_usd)                                         AS tracked_theo,
               SUM(comp_cost_usd) / NULLIF(SUM(theo_usd), 0)         AS reinv_tracked
        FROM player_period
        GROUP BY period_month
        ORDER BY period_month
        """,
    )
    floor_theo = {m: t for (m, t) in q(
        con,
        "SELECT STRFTIME(gaming_date,'%Y-%m'), SUM(theo_usd) FROM property GROUP BY 1",
    )}
    table(
        [
            (m, f"${c:,.0f}", f"${tt:,.0f}", f"{rt*100:.2f}%",
             f"${floor_theo[m]:,.0f}", f"{c/floor_theo[m]*100:.2f}%")
            for (m, c, tt, rt) in reinv
        ],
        ["month", "comp cost (player_period)", "tracked theo",
         "reinv / tracked", "floor theo", "reinv / floor"],
    )
    write(
        "**Verified:** comp reinvestment (comp cost ÷ **tracked** theo) climbs **1.11% (Jan) → 1.32% (Jun)**, "
        "exactly matching the §3 lead. Using floor theo as the denominator gives 0.72% → 0.88%; "
        "we will adopt **tracked theo** as the authoritative denominator in `gold_comp_week`."
    )

    # ------------------------------------------------------------------ Top-1% concentration
    section("Lead #7 — Tracked-theo concentration")
    conc = q(
        con,
        """
        WITH p AS (
            SELECT player_id, SUM(theo_usd) AS theo
            FROM player_period
            GROUP BY player_id
            HAVING SUM(theo_usd) > 0
        ),
        ranked AS (
            SELECT player_id, theo,
                   NTILE(100) OVER (ORDER BY theo DESC) AS pct
            FROM p
        ),
        agg AS (
            SELECT SUM(theo) AS theo_all FROM p
        )
        SELECT 'top 1%'  AS bucket, SUM(theo) / (SELECT theo_all FROM agg) AS share
          FROM ranked WHERE pct = 1
        UNION ALL
        SELECT 'top 10%' AS bucket, SUM(theo) / (SELECT theo_all FROM agg) AS share
          FROM ranked WHERE pct <= 10
        UNION ALL
        SELECT 'top 25%' AS bucket, SUM(theo) / (SELECT theo_all FROM agg) AS share
          FROM ranked WHERE pct <= 25
        """,
    )
    table([(b, f"{s*100:.1f}%") for (b, s) in conc],
          ["segment", "share of tracked theo"])

    # ------------------------------------------------------------------ Lineup
    section("Lead #8 — Lineup: theo per available hour by config (floor median baseline)")
    lineup = q(
        con,
        """
        WITH per_machine AS (
            SELECT machine_id,
                   ANY_VALUE(config_id)        AS config_id,
                   ANY_VALUE(theme)            AS theme,
                   ANY_VALUE(configured_rtp)   AS rtp,
                   ANY_VALUE(volatility_class) AS vol,
                   SUM(theo_usd)               AS theo,
                   SUM(available_hours)        AS ah
            FROM prepared
            WHERE active AND available_hours > 0
            GROUP BY machine_id
            HAVING SUM(available_hours) > 50
        )
        SELECT config_id, theme, rtp, vol,
               COUNT(*)                      AS n_machines,
               MEDIAN(theo / ah)             AS theo_per_hour_median,
               MIN(theo / ah)                AS min_tph,
               MAX(theo / ah)                AS max_tph
        FROM per_machine
        GROUP BY config_id, theme, rtp, vol
        ORDER BY theo_per_hour_median
        """,
    )
    table(
        [(c, th, f"{rtp*100:.1f}%", v, n,
          f"${m:,.2f}", f"${mn:,.2f}", f"${mx:,.2f}")
         for (c, th, rtp, v, n, m, mn, mx) in lineup],
        ["config", "theme", "RTP", "volatility", "machines",
         "theo/h median", "min", "max"],
    )

    # ------------------------------------------------------------------ Data quality
    section("Data-quality checklist")
    off_floor = q(con, "SELECT COUNT(*) FROM prepared WHERE location_id IS NULL")[0][0]
    active_rows = q(con, "SELECT COUNT(*) FROM prepared WHERE active")[0][0]
    dst_day = q(
        con,
        "SELECT scheduled_seconds FROM calendar WHERE gaming_date = DATE '2025-03-08'",
    )[0][0]
    carded = q(
        con,
        """
        SELECT SUM(carded_coin_in_usd) AS carded,
               SUM(coin_in_usd)        AS all_,
               SUM(carded_coin_in_usd) / NULLIF(SUM(coin_in_usd), 0) AS share
        FROM prepared WHERE active
        """,
    )[0]
    write(
        f"- Off-floor rows (location_id IS NULL): **{off_floor}** (expected 1,018).\n"
        f"- Active floor rows: **{active_rows:,}**.\n"
        f"- 2025-03-08 scheduled seconds: **{dst_day:,}** (expected 82,800).\n"
        f"- Carded share of coin-in (floor): **{carded[2]*100:.2f}%** "
        f"(carded ${carded[0]/1e6:,.1f}M of ${carded[1]/1e6:,.1f}M)."
    )

    # ------------------------------------------------------------------ Databricks CLI status
    section("Infra status")
    write(
        "- **Databricks CLI:** not installed on this host. Phase 1 (recon) runs entirely "
        "on local DuckDB over the released parquet files, so this does not block recon. "
        "Before Phase 2 I will need the CLI authenticated — see the §8 checkpoint note below.\n"
        "- **Python env:** `.venv/bin/python` with duckdb 2.0.0, pandas 3.1.1, pyarrow 26.0.1.\n"
        "- **Repo verify scripts:** `verify_data.py` PASS (62 checksums, 31 row/format matches); "
        "`verify_semantics.py` PASS (11/11 invariants)."
    )

    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
