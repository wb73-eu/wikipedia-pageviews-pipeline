WITH staged AS (
    SELECT *
    FROM {{ ref('stg_pageviews') }}
),

latest_hour AS (
    SELECT MAX(viewed_at) AS max_hour
    FROM staged
),

top_articles AS (
    SELECT
        s.page_title,
        s.view_count,
        s.viewed_at
    FROM staged s
    JOIN latest_hour l ON s.viewed_at = l.max_hour
    ORDER BY view_count DESC
    LIMIT 100
)

SELECT * FROM top_articles