# -*- coding: utf-8 -*-
# This migration script will run after the module update
# It will ensure the system parameters are properly set up

import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Ensure system parameters are properly set up after migration
    """
    # Set default values for system parameters
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('openwebui.base_url', 'https://ai.bemade.org/api', now(), now())
        ON CONFLICT (key) DO NOTHING
    """)
    
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('openwebui.model', 'anthropic.claude-3-7-sonnet-latest', now(), now())
        ON CONFLICT (key) DO NOTHING
    """)
    
    # Log the migration
    cr.execute("""
        INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
        VALUES (now(), 1, 'openwebui_connector', 'server', current_database(), 'info', 
               'Post-migration: Set default system parameters', 
               '/addons/openwebui_connector/migrations/1.0/post-migration.py', 30, 'migrate')
    """)
    
    # Check if helpdesk_sale_order_ai module is installed
    cr.execute("""
        SELECT id FROM ir_module_module 
        WHERE name = 'helpdesk_sale_order_ai' 
        AND state = 'installed'
    """)
    
    if cr.fetchone():
        _logger.info("helpdesk_sale_order_ai module is installed, ensuring parameters are set")
        
        # Ensure the helpdesk AI parameter exists
        cr.execute("""
            INSERT INTO ir_config_parameter (key, value, create_date, write_date)
            VALUES ('helpdesk_sale_order_ai.use_ai_sale_orders', 'False', now(), now())
            ON CONFLICT (key) DO NOTHING
        """)
        
        # Log the migration
        cr.execute("""
            INSERT INTO ir_logging(create_date, create_uid, name, type, dbname, level, message, path, line, func)
            VALUES (now(), 1, 'openwebui_connector', 'server', current_database(), 'info', 
                   'Post-migration: Set default helpdesk AI parameters', 
                   '/addons/openwebui_connector/migrations/1.0/post-migration.py', 50, 'migrate')
        """)
