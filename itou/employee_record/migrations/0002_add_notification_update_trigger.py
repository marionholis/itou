# Generated by Django 4.0.3 on 2022-03-11 21:52

from django.db import migrations


class Migration(migrations.Migration):
    replaces = [("employee_record", "0013_add_notification_update_trigger")]

    dependencies = [
        ("employee_record", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- Create a partial index that will act as a compound
                -- unique constraint for UPSERTs
                -- GOAL: only allow one NEW notification for a given type, employee record pair
                CREATE UNIQUE INDEX partial_unique_new_notification
                    ON employee_record_employeerecordupdatenotification (employee_record_id, notification_type)
                    WHERE status = 'NEW';

                CREATE OR REPLACE FUNCTION create_employee_record_approval_notification()
                    RETURNS TRIGGER AS $approval_notification$
                    DECLARE
                        -- Must be declared for iterations
                        current_employee_record_id INT;
                    BEGIN
                        -- If there is an "UPDATE" action on 'approvals_approval' table (Approval model object):
                        -- create an `EmployeeRecordUpdateNotification` object for each PROCESSED `EmployeeRecord`
                        -- linked to this approval
                        IF (TG_OP = 'UPDATE') THEN
                            -- Only for update operations:
                            -- iterate through processed employee records linked to this approval
                            FOR current_employee_record_id IN
                                SELECT id FROM employee_record_employeerecord
                                WHERE approval_number = NEW.number
                                AND status = 'PROCESSED'
                                LOOP
                                    -- Create `EmployeeRecordUpdateNotification` object
                                    -- with the correct type and status
                                    INSERT INTO employee_record_employeerecordupdatenotification
                                        (employee_record_id, created_at, updated_at, status, notification_type)
                                    SELECT current_employee_record_id, NOW(), NOW(), 'NEW', 'APPROVAL'
                                    -- Update it if already created (UPSERT)
                                    -- On partial indexes conflict, the where clause of the index must be added here
                                    ON conflict(employee_record_id, notification_type) WHERE status = 'NEW'
                                    DO
                                    -- Not exactly the same syntax as a standard update op
                                    UPDATE SET updated_at = NOW();
                                END LOOP;
                        END IF;
                        RETURN NULL;
                    END;
                $approval_notification$ LANGUAGE plpgsql;


                CREATE TRIGGER trigger_employee_record_approval_update_notification
                AFTER UPDATE OF start_at,end_at ON approvals_approval
                FOR EACH ROW
                -- an UPDATE operation will activate the trigger if 'end_at' or 'start_at' is targeted,
                -- even if their value has not changed !
                -- Thus the need of a WHEN clause :
                WHEN (OLD.end_at    IS DISTINCT FROM NEW.end_at
                      OR OLD.start_at IS DISTINCT FROM NEW.start_at)
                EXECUTE PROCEDURE create_employee_record_approval_notification();
                """,
            reverse_sql="""
                        DROP TRIGGER IF EXISTS trigger_employee_record_approval_update_notification
                            ON approvals_approval;
                        DROP FUNCTION IF EXISTS create_employee_record_approval_notification();
                        DROP INDEX IF EXISTS partial_unique_new_notification;
                        """,
        )
    ]
