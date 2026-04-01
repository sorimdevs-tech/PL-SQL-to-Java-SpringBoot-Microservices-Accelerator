-- Test file to simulate mortenbra repo (no CREATE TABLE, only procedures with DML)

CREATE PROCEDURE RECONCILIATION_CHECK_DIFF
(
        pt_rec_grp IN VARCHAR2,
        pt_all     IN VARCHAR2 DEFAULT 'Y'
)
IS
    -- Cursor
    CURSOR cur_differences IS
        SELECT difference_id, reason,
               account_from, account_to,
               amount, status
        FROM RECONCILIATION_DIFFERENCES
        WHERE rec_group = pt_rec_grp
        ORDER BY diff_id;

    v_count NUMBER;

BEGIN
    -- Do some operations on tables that don't have DDL in this file
    INSERT INTO RECONCILIATION_LOG (rec_time, rec_group, status, message)
    VALUES (SYSDATE, pt_rec_grp, 'START', 'Checking differences');

    FOR rec IN cur_differences LOOP
        UPDATE RECONCILIATION_DIFFERENCES
        SET processed = SYSDATE
        WHERE difference_id = rec.difference_id;

        DELETE FROM RECONCILIATION_TEMP
        WHERE temp_id = rec.difference_id;

        INSERT INTO RECONCILIATION_AUDIT (audit_date, action, rec_group, amount)
        VALUES (SYSDATE, 'DELETE', pt_rec_grp, rec.amount);
    END LOOP;

    COMMIT;

END RECONCILIATION_CHECK_DIFF;
/

CREATE PROCEDURE PROCESS_ALL_RECONCILIATIONS
IS
BEGIN
    -- References more tables without DDL
    DELETE FROM RECONCILIATION_QUEUE WHERE status = 'COMPLETED';

    INSERT INTO RECONCILIATION_STATS (stat_date, total_processed)
    SELECT SYSDATE, COUNT(*) FROM RECONCILIATION_LOG;

    COMMIT;
END;
/
