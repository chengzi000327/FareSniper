CREATE OR REPLACE VIEW v_h1_chat_vs_form AS
SELECT payload->>'arm' AS arm,
       AVG(CASE WHEN event_name = 'result_viewed' THEN 1.0 ELSE 0 END) AS completion_rate
FROM analytics_events
WHERE payload->>'arm' IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE VIEW v_h2_advice_adoption AS
SELECT date_trunc('day', created_at) AS day,
       (COUNT(*) FILTER (WHERE event_name='ticket_clicked' AND payload->>'has_signals'='true'))::float
       / NULLIF(COUNT(*) FILTER (WHERE event_name='result_viewed' AND payload->>'has_signals'='true'), 0)
       AS adoption_rate
FROM analytics_events
GROUP BY 1;

CREATE OR REPLACE VIEW v_h3_jump_rate AS
SELECT date_trunc('day', created_at) AS day,
       COUNT(*) FILTER (WHERE event_name='purchase_jumped')::float
       / NULLIF(COUNT(*) FILTER (WHERE event_name='result_viewed'), 0) AS jump_rate
FROM analytics_events GROUP BY 1;

CREATE OR REPLACE VIEW v_h4_pref_retention AS
SELECT 'all' AS cohort,
       COUNT(DISTINCT user_id) AS users,
       COUNT(DISTINCT CASE WHEN created_at >= (SELECT MIN(created_at) FROM analytics_events) + interval '7 day'
                           THEN user_id END) AS d7_active
FROM analytics_events;

CREATE OR REPLACE VIEW v_h5_freshness_nps AS
SELECT date_trunc('week', created_at) AS week,
       AVG((payload->>'nps')::int) AS nps_avg
FROM analytics_events WHERE event_name='nps_submitted' GROUP BY 1;

CREATE OR REPLACE VIEW v_h6_explore_traffic AS
SELECT date_trunc('day', created_at) AS day,
       COUNT(*) FILTER (WHERE payload->>'source'='explore')::float
       / NULLIF(COUNT(*) FILTER (WHERE event_name='search_submitted'), 0) AS explore_share
FROM analytics_events GROUP BY 1;
