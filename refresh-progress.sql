-- Reads per-student MobyMax Reading Hole-Filling activity for the 11 students
-- with custom plans. Save the `data` array of the result as JSON to
-- /tmp/activity_records.json, then run refresh-progress.py.
--
-- Notes:
--   - Course-name match is the new format only (`[Mobymax] Reading G<grade>
--     hole-filling`). Eddie's legacy `MobyMax - Reading Skills … Hole-Filling`
--     records came from earlier manual plans and don't count toward his
--     current custom plan, so they're intentionally excluded.
--   - Date filter is per-student (>= each student's plan creation date).
--   - "Assignment Complete: …" rows are dropped (they have null
--     correct/total_questions and aren't lessons).
SELECT
  CASE a.student_id
    WHEN 'addf1ed8-19e9-471a-b784-814522d4496c' THEN 'ada'
    WHEN 'bf7d285f-d5b3-4841-ae03-a426437ee1de' THEN 'eddie'
    WHEN '5db81eab-f06f-421e-a897-6dbf82f1e091' THEN 'edgar-shinar'
    WHEN 'd2d9fe9c-6d3c-4130-8c9d-244bba4bac04' THEN 'elena'
    WHEN '554fbaed-24f8-434f-8ecd-d013fc8430b6' THEN 'emma'
    WHEN '70def859-5182-4421-8161-ba1b6b4c17ba' THEN 'jacob'
    WHEN '82ccf6c2-2904-45da-9bb2-2e92009b9d79' THEN 'jaya'
    WHEN '11c3eec8-6a8c-4164-94a5-53fbf45220e3' THEN 'keaton'
    WHEN '00d46de9-f30d-4c64-a62f-631c5a787e22' THEN 'lily'
    WHEN 'a3cec910-95d2-4c59-85e3-10e58289c42a' THEN 'marcus'
    WHEN '86a50290-bd1e-417f-955c-c80f86475959' THEN 'teddy'
  END AS slug,
  a.activity_name,
  a.calendar_date::date AS d,
  a.correct_questions,
  a.total_questions,
  a.is_school_day,
  a.course_name
FROM rpt2_activity_log a
WHERE
  ( (a.student_id = 'addf1ed8-19e9-471a-b784-814522d4496c' AND a.calendar_date::date >= '2026-05-04')
 OR (a.student_id = 'bf7d285f-d5b3-4841-ae03-a426437ee1de' AND a.calendar_date::date >= '2026-03-27')
 OR (a.student_id = '5db81eab-f06f-421e-a897-6dbf82f1e091' AND a.calendar_date::date >= '2026-04-13')
 OR (a.student_id = 'd2d9fe9c-6d3c-4130-8c9d-244bba4bac04' AND a.calendar_date::date >= '2026-05-04')
 OR (a.student_id = '554fbaed-24f8-434f-8ecd-d013fc8430b6' AND a.calendar_date::date >= '2026-04-29')
 OR (a.student_id = '70def859-5182-4421-8161-ba1b6b4c17ba' AND a.calendar_date::date >= '2026-05-04')
 OR (a.student_id = '82ccf6c2-2904-45da-9bb2-2e92009b9d79' AND a.calendar_date::date >= '2026-03-26')
 OR (a.student_id = '11c3eec8-6a8c-4164-94a5-53fbf45220e3' AND a.calendar_date::date >= '2026-04-29')
 OR (a.student_id = '00d46de9-f30d-4c64-a62f-631c5a787e22' AND a.calendar_date::date >= '2026-05-04')
 OR (a.student_id = 'a3cec910-95d2-4c59-85e3-10e58289c42a' AND a.calendar_date::date >= '2026-04-29')
 OR (a.student_id = '86a50290-bd1e-417f-955c-c80f86475959' AND a.calendar_date::date >= '2026-05-07')
  )
  AND (
    a.course_name ILIKE '[Mobymax] Reading G%hole-filling'
    OR a.course_name ILIKE 'Reading Primer Grade%'
  )
  AND a.activity_name NOT ILIKE 'Assignment Complete:%'
ORDER BY 1, d, activity_name
