CREATE OR REPLACE TABLE workspace.royale.player_period USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/player_period.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.prepared_daily_view USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/prepared_daily_view.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.property_day USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/property_day.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.action_catalog USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/action_catalog.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.calendar_day USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/calendar_day.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.cost_rules USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/cost_rules.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.floor_locations USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/floor_locations.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.floor_walkways USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/floor_walkways.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.game_math USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/game_math.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.machine_day USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/machine_day.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.machines USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/machines.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.operations USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/operations.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.placements USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/placements.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.fnb_transactions USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/fnb_transactions.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.loyalty_ledger USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/loyalty_ledger.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.players USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/players.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.sessions USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/sessions.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.trips USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/trips.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.events USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/events.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.benchmark_property_monthly USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/benchmark_property_monthly.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.benchmark_public USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/benchmark_public.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.benchmark_state_monthly USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/benchmark_state_monthly.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.city_visitation_monthly USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/city_visitation_monthly.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.visitor_profile_segments USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/visitor_profile_segments.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.visitor_profile_summary USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/visitor_profile_summary.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.weather_daily USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/weather_daily.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.zone_traffic_hourly USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/zone_traffic_hourly.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.machine_hour USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/machine_hour.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.security_incidents USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/security_incidents.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.shift_roster USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/shift_roster.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.royale.visitor_profile_monthly USING DELTA AS
SELECT * FROM read_files('/Volumes/workspace/royale/raw/visitor_profile_monthly.parquet', format => 'parquet');
