-- 1
INSERT INTO hr.promotion (deptnum, empname, yearsexp)
SELECT deptno, name, yrsexp
FROM hr.employee
WHERE yrsexp > 10;

--
SELEC FROM;
-- 2
INSERT INTO silver_layer.target_table_xyz
SELECT *
FROM bronze_layer.source_table_abc AS src_a
INNER JOIN bronze_layer.source_table_abc_hist AS src_hist
    ON src_a.id = src_hist.id;

-- 3
CREATE TABLE credit_risk.exposure_daily AS
SELECT c.customer_id, c.exposure_amt, r.rating
FROM staging.counterparty_exposure c
INNER JOIN staging.counterparty_rating r
    ON c.customer_id = r.customer_id;

-- 4
MERGE INTO gold_internal.target_sales AS tgt
USING (
    SELECT
        s.sale_id,
        s.customer_id,
        c.customer_region,
        s.sale_amount
    FROM silver_internal.staging_sales AS s
    INNER JOIN gold_internal.customer_dim AS c
        ON s.customer_id = c.customer_id
    WHERE s.status = 'COMPLETED'
) AS src
ON tgt.sale_id = src.sale_id  -- Must match the Primary Index of target_sales
WHEN MATCHED THEN
    UPDATE SET
        customer_region = src.customer_region,
        sale_amount = src.sale_amount
WHEN NOT MATCHED THEN
    INSERT (sale_id, customer_id, customer_region, sale_amount)
    VALUES (src.sale_id, src.customer_id, src.customer_region, src.sale_amount);

-- 5
CREATE MULTISET VOLATILE TABLE vt_collateral AS (
    SEL collateral_id, customer_id, collateral_value
    FROM raw.collateral_feed
    WHERE load_ts > CURRENT_DATE - 1
) WITH DATA PRIMARY INDEX (collateral_id)
ON COMMIT PRESERVE ROWS;

--

-- 5
CREATE MULTISET VOLATILE TABLE vt_collateral2 AS (
    SEL collateral_id, customer_id, collateral_value
    FROM raw.collateral_feed AS cf
    INNER JOIN  raw.collateral_feed_hist AS cfh
    ON cf.collateral_id = cfh.collateral_id
    WHERE load_ts > CURRENT_DATE - 1
) WITH DATA PRIMARY INDEX (collateral_id)
ON COMMIT PRESERVE ROWS;

-- 6
INS INTO gold.risk_report_daily (customer_id, exposure_amt, collateral_value, rating)
SEL e.customer_id, e.exposure_amt, v.collateral_value, e.rating
FROM credit_risk.exposure_daily e
LEFT OUTER JOIN vt_collateral v
    ON e.customer_id = v.customer_id
QUALIFY ROW_NUMBER() OVER (PARTITION BY e.customer_id ORDER BY e.exposure_amt DESC) = 1;

--
INS INTO gold.risk_report_daily2 (customer_id, exposure_amt, collateral_value, rating)
SEL e.customer_id, e.exposure_amt, v.collateral_value, e.rating
FROM credit_risk.exposure_daily e
LEFT OUTER JOIN vt_collateral2 v
    ON e.customer_id = v.customer_id
QUALIFY ROW_NUMBER() OVER (PARTITION BY e.customer_id ORDER BY e.exposure_amt DESC) = 1;

-- 7
EXEC risk_macros.refresh_regulatory_extract('CREDIT', CURRENT_DATE);

-- 8
SELECT * FROM silver_layer.source_table_asdf;