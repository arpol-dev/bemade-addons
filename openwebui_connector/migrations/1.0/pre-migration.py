# -*- coding: utf-8 -*-
# This migration script will run before the module update
# It will handle database constraints and column issues for Odoo 18 compatibility

def migrate(cr, version):
    """
    Handle database constraints and column issues for Odoo 18 compatibility
    """
    # 1. Check and drop any foreign key constraints on helpdesk_ai_prompt_template_id
    cr.execute("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_name = 'res_config_settings'
        AND ccu.column_name = 'helpdesk_ai_prompt_template_id'
        AND tc.constraint_type = 'FOREIGN KEY'
    """)
    
    constraints = cr.fetchall()
    for constraint in constraints:
        constraint_name = constraint[0]
        # Drop the constraint
        cr.execute(f"""
            ALTER TABLE res_config_settings 
            DROP CONSTRAINT IF EXISTS {constraint_name}
        """)
        
        # Log the migration
        cr.execute("""
            INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
            VALUES (now(), 1, 'openwebui_connector', 'server', current_database(), 'info', 
                   'Migration: Dropped foreign key constraint: %s', 
                   '/addons/openwebui_connector/migrations/1.0/pre-migration.py', 30, 'migrate')
        """, (constraint_name,))
    
    # 2. Check if the column exists and drop it if needed
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'res_config_settings' 
        AND column_name = 'helpdesk_ai_prompt_template_id'
    """)
    
    if cr.fetchone():
        # We need to drop the column to avoid conflicts with the new field
        try:
            cr.execute("""
                ALTER TABLE res_config_settings 
                DROP COLUMN IF EXISTS helpdesk_ai_prompt_template_id
            """)
            
            # Log the migration
            cr.execute("""
                INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
                VALUES (now(), 1, 'openwebui_connector', 'server', current_database(), 'info', 
                       'Migration: Dropped column helpdesk_ai_prompt_template_id', 
                       '/addons/openwebui_connector/migrations/1.0/pre-migration.py', 50, 'migrate')
            """)
        except Exception as e:
            # Log the error
            cr.execute("""
                INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
                VALUES (now(), 1, 'openwebui_connector', 'server', current_database(), 'error', 
                       'Migration error: %s', 
                       '/addons/openwebui_connector/migrations/1.0/pre-migration.py', 60, 'migrate')
            """, (str(e),))
