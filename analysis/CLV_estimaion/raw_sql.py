RETENTION_OF_OTT_AND_ROLE = """
WITH user_dday AS (SELECT m.user_id,
                          MIN(m.create_at)                        AS first_start_at,
                          EXTRACT(DAY FROM MIN(m.create_at))::INT AS dday_after_2days
                   FROM member_and_host m
                    -- WHERE 1=1
                    -- and m.ott_service_id = 6 -- ANY (p_ott_service_ids) -- ott_service_id 선택
                    -- and m.is_host=true
                   GROUP BY m.user_id),

     dday_2_list AS (SELECT u.user_id,
                            u.first_start_at,
                            GENERATE_SERIES(u.first_start_at::DATE, date(NOW()), '1 month'::INTERVAL) AS dday,
                            GENERATE_SERIES(u.first_start_at::DATE, date(NOW()), '1 month'::INTERVAL) +
                            INTERVAL '2 days'                                                         AS dday_after_2days
                     FROM user_dday u
                     where first_start_at::date >= '2023-01-01'
                     ORDER BY u.user_id, dday),

     result AS (SELECT ROW_NUMBER() OVER (PARTITION BY d.user_id ORDER BY d.dday_after_2days) - 1     AS n_value,
                       d.user_id,
                       (EXTRACT(YEAR FROM d.first_start_at) || '-' ||
                        EXTRACT(MONTH FROM d.first_start_at))::VARCHAR                                AS first_month,
                       d.first_start_at,
                       d.dday::DATE                                                                   AS dday_date,
                       d.dday_after_2days::DATE                                                       AS dday_after_2days_date,
                       (SELECT COUNT(*)
                        FROM member_and_host a
                        WHERE a.user_id = d.user_id
                          AND a.create_at::DATE <= d.dday_after_2days::DATE -- 2일 정시가 되는 순간에 존재했던 행
                          AND (a.delete_at IS NULL OR a.delete_at::DATE >= d.dday_after_2days::DATE)) AS cnt
                FROM dday_2_list d),

     final as (SELECT r.n_value,
                      r.user_id,
                      r.first_month,
                      r.first_start_at,
                      r.dday_date,
                      r.dday_after_2days_date,
                      r.cnt,
                      CASE
                          WHEN r.cnt > 0
                              THEN 'O'::CHAR
                          WHEN r.cnt = 0 AND
                               EXTRACT(YEAR FROM r.dday_date) || '-' || EXTRACT(MONTH FROM r.dday_date) =
                               r.first_month
                              THEN 'O'::CHAR
                          ELSE
                              'X'::CHAR
                          END AS is_using
               FROM result r),

     exclude_last_mo as (select first_month, max(n_value) n_value
                     from final
                     group by 1),

     survivors AS   (select f.first_month,
                           f.n_value,
                           count(distinct user_id) cnt
                    from final f
                    where is_using = 'O'
                      and not exists (select first_month, n_value
                                      from exclude_last_mo e
                                      where e.first_month = f.first_month
                                        and e.n_value = f.n_value)
                    group by 1, 2),

     first_users AS (SELECT     first_month
                            ,   MAX(cnt) AS max_cnt
                     FROM       survivors
                     GROUP BY   first_month),

    survive_rate AS (SELECT     survivors.*
                            ,   first_users.max_cnt
                     FROM       survivors
                                LEFT JOIN first_users
                                ON  survivors.first_month = first_users.first_month)

SELECT *,cnt / max_cnt::FLOAT AS retention FROM survive_rate
"""