# -*- coding: utf-8 -*-
# This migration script will run before the module update
# It will handle database constraints and prepare for the migration

import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Handle database constraints and prepare for migration
    """
    if not version:
        return

    _logger.info("Starting pre-migration for openwebui_connector")
    
    # 1. Drop foreign key constraints on ai_prompt_template_id to avoid conflicts
    cr.execute("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_name = 'res_config_settings'
        AND ccu.column_name = 'ai_prompt_template_id'
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
        _logger.info(f"Dropped foreign key constraint: {constraint_name}")
    
    # 2. Update system parameters to use new naming
    cr.execute("""
        UPDATE ir_config_parameter
        SET key = REPLACE(key, 'openai.', 'openwebui.')
        WHERE key LIKE 'openai.%'
    """)
    
    # 3. Check if the old openai_prompt_template table exists
    cr.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'openai_prompt_template')")
    if cr.fetchone()[0]:
        # Create a backup of the data if needed
        cr.execute("""
            CREATE TABLE IF NOT EXISTS openai_prompt_template_backup AS
            SELECT * FROM openai_prompt_template
        """)
        _logger.info("Created backup of openai_prompt_template data")
        
    _logger.info("Pre-migration completed successfully")
