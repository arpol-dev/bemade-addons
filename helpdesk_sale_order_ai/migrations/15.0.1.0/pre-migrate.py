# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Migrate system parameters from helpdesk OpenWebUI client to centralized OpenAI client
    """
    if not version:
        return

    _logger.info("Starting migration of OpenWebUI configuration parameters")
    
    # Map of old parameter keys to new parameter keys
    param_mapping = {
        'openwebui.api_key': 'openai.api_key',
        'openwebui.base_url': 'openai.base_url',
        'openwebui.model': 'openai.model',
    }
    
    # For each parameter, check if it exists and migrate it if needed
    for old_key, new_key in param_mapping.items():
        # Check if the old parameter exists
        cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (old_key,))
        old_value = cr.fetchone()
        
        if old_value and old_value[0]:
            # Check if the new parameter already exists
            cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (new_key,))
            new_value = cr.fetchone()
            
            if not new_value or not new_value[0]:
                # New parameter doesn't exist or is empty, set it to the old value
                _logger.info(f"Migrating parameter {old_key} to {new_key} with value {old_value[0]}")
                
                cr.execute("""
                    INSERT INTO ir_config_parameter (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (new_key, old_value[0]))
    
    _logger.info("Migration of OpenWebUI configuration parameters completed")
