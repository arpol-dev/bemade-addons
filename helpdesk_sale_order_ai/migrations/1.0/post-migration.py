# -*- coding: utf-8 -*-
# This migration script will run after the module update
# It will ensure the prompt templates are properly set up

import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Ensure prompt templates are properly set up after migration
    """
    # Check if we have any prompt templates
    cr.execute("""
        SELECT COUNT(*) FROM helpdesk_ai_prompt_template
    """)
    
    template_count = cr.fetchone()[0]
    
    if template_count == 0:
        # Create a default template if none exists
        _logger.info("No prompt templates found, creating default template")
        
        default_template_name = "Default Sales Order Template"
        default_template_content = """
You are a sales order assistant. Your task is to analyze the customer's request and suggest products or services that would meet their needs.

Please provide a list of products or services in the following format:
1. Product Name | Quantity | Description
2. Product Name | Quantity | Description

If you're not sure about a specific product, suggest a generic service item with a description of what it should accomplish.
"""
        
        # Insert the default template
        cr.execute("""
            INSERT INTO helpdesk_ai_prompt_template (name, content, create_date, write_date)
            VALUES (%s, %s, now(), now())
            RETURNING id
        """, (default_template_name, default_template_content))
        
        template_id = cr.fetchone()[0]
        
        # Set this as the default template
        cr.execute("""
            INSERT INTO ir_config_parameter (key, value, create_date, write_date)
            VALUES ('helpdesk_sale_order_ai.default_prompt_template_id', %s, now(), now())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (str(template_id),))
        
        # Log the migration
        cr.execute("""
            INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
            VALUES (now(), 1, 'helpdesk_sale_order_ai', 'server', current_database(), 'info', 
                   'Post-migration: Created default prompt template with ID ' || %s, 
                   '/addons/helpdesk_sale_order_ai/migrations/1.0/post-migration.py', 50, 'migrate')
        """, (str(template_id),))
    else:
        # Check if we have a default template set
        cr.execute("""
            SELECT value FROM ir_config_parameter
            WHERE key = 'helpdesk_sale_order_ai.default_prompt_template_id'
        """)
        
        default_template_id = cr.fetchone()
        
        if not default_template_id:
            # Get the first template and set it as default
            cr.execute("""
                SELECT id FROM helpdesk_ai_prompt_template
                ORDER BY id ASC
                LIMIT 1
            """)
            
            template_id = cr.fetchone()[0]
            
            # Set this as the default template
            cr.execute("""
                INSERT INTO ir_config_parameter (key, value, create_date, write_date)
                VALUES ('helpdesk_sale_order_ai.default_prompt_template_id', %s, now(), now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (str(template_id),))
            
            # Log the migration
            cr.execute("""
                INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
                VALUES (now(), 1, 'helpdesk_sale_order_ai', 'server', current_database(), 'info', 
                       'Post-migration: Set existing template with ID ' || %s || ' as default', 
                       '/addons/helpdesk_sale_order_ai/migrations/1.0/post-migration.py', 75, 'migrate')
            """, (str(template_id),))
        else:
            _logger.info(f"Default prompt template already set: {default_template_id[0]}")
            
    # Ensure the system parameters are properly set up
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('openai.base_url', 'https://ai.bemade.org/api', now(), now())
        ON CONFLICT (key) DO NOTHING
    """)
    
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('openai.model', 'anthropic.claude-3-7-sonnet-latest', now(), now())
        ON CONFLICT (key) DO NOTHING
    """)
