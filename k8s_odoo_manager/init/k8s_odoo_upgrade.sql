CREATE OR REPLACE VIEW k8s_odoo_upgrade AS
SELECT
    0 AS id,
    NULL::integer AS instance_id,
    NULL::integer AS cluster_id,
    NULL::varchar AS job_name,
    NULL::varchar AS display_name,
    NULL::varchar AS state,
    NULL::timestamp AS scheduled_date,
    NULL::timestamp AS start_date,
    NULL::timestamp AS end_date,
    NULL::float AS duration,
    NULL::varchar AS modules,
    NULL::varchar AS database,
    NULL::varchar AS status_message,
    NULL::text AS log
WHERE 1=0; -- Empty view by default
