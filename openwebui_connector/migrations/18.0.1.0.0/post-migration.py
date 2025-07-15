# -*- coding: utf-8 -*-
# This migration script will run after the module update
# It will migrate data from openai_prompt_template to openwebui_prompt_template

import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Migrate data from openai_prompt_template to openwebui_prompt_template
    """
    if not version:
        return

    _logger.info("Starting migration of prompt templates from openai to openwebui")
    
    # Check if the old table exists
    cr.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'openai_prompt_template')")
    if not cr.fetchone()[0]:
        _logger.info("No openai_prompt_template table found, skipping migration")
        return
    
    # Check if there's data to migrate
    cr.execute("SELECT COUNT(*) FROM openai_prompt_template")
    count = cr.fetchone()[0]
    _logger.info(f"Found {count} records to migrate from openai_prompt_template")
    
    if count > 0:
        # Copy data from old table to new table
        cr.execute("""
            INSERT INTO openwebui_prompt_template (
                id, name, content, is_default, module, create_uid, create_date, write_uid, write_date
            )
            SELECT 
                id, name, content, is_default, module, create_uid, create_date, write_uid, write_date
            FROM 
                openai_prompt_template
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                content = EXCLUDED.content,
                is_default = EXCLUDED.is_default,
                module = EXCLUDED.module,
                write_uid = EXCLUDED.write_uid,
                write_date = EXCLUDED.write_date
        """)
        
        # Update sequence if needed
        cr.execute("""
            SELECT MAX(id) FROM openwebui_prompt_template
        """)
        max_id = cr.fetchone()[0] or 0
        if max_id > 0:
            cr.execute(f"""
                SELECT setval('openwebui_prompt_template_id_seq', {max_id})
            """)
        
        # Log the migration
        _logger.info(f"Successfully migrated {count} records from openai_prompt_template to openwebui_prompt_template")
        
        # Update any references in res_config_settings
        cr.execute("""
            UPDATE ir_config_parameter
            SET key = REPLACE(key, 'openai.', 'openwebui.')
            WHERE key LIKE 'openai.%'
        """)
        
        # Update any references to prompt template IDs in system parameters
        cr.execute("""
            UPDATE ir_config_parameter
            SET key = REPLACE(key, 'openai_prompt_template_id', 'openwebui_prompt_template_id')
            WHERE key LIKE '%openai_prompt_template_id%'
        """)
        
        _logger.info("Updated system parameters to use openwebui prefix")
