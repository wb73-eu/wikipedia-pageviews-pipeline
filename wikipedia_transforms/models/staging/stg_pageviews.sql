WITH source AS (
    SELECT *
    FROM {{source('wikipedia_raw', 'pageviews')}}
),

renamed AS (
    SELECT
        language_code,
        page_title,
        view_count,
        response_size,
        viewed_at
    FROM source
    WHERE language_code = 'en'
        AND view_count > 0
        AND page_title != 'Main_Page'
        AND page_title != '-'
        AND page_title NOT LIKE 'Special:%'
        AND page_title NOT LIKE 'Talk:%'
        AND page_title NOT LIKE 'User:%'
        AND page_title NOT LIKE 'File:%'
        AND page_title NOT LIKE 'Wikipedia:%'
        AND page_title NOT LIKE 'Portal:%'
)

SELECT * FROM renamed
