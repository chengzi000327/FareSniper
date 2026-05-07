-- backend/analytics/metrics_views.sql
-- North-star (QPC) and conversion-funnel views over analytics_events.
-- Re-runnable: every CREATE uses OR REPLACE so the migration is idempotent.

CREATE OR REPLACE VIEW v_monthly_qpc AS
SELECT
    date_trunc('month', created_at) AS month_start,
    COUNT(*) FILTER (WHERE event_name = 'purchase_jumped') AS qpc
FROM analytics_events
GROUP BY 1;

CREATE OR REPLACE VIEW v_search_funnel AS
SELECT
    date_trunc('day', created_at) AS day,
    COUNT(*) FILTER (WHERE event_name = 'search_submitted') AS search_count,
    COUNT(*) FILTER (WHERE event_name = 'result_viewed')    AS result_count,
    COUNT(*) FILTER (WHERE event_name = 'ticket_clicked')   AS click_count,
    COUNT(*) FILTER (WHERE event_name = 'purchase_jumped')  AS purchase_count
FROM analytics_events
GROUP BY 1;
