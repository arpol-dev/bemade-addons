# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Migrate helpdesk.ai.prompt.template records to openwebui.prompt.template
    """
    if not version:
        return

    _logger.info("Starting migration of AI prompt templates")
    
    # Check if the old model exists
    cr.execute("SELECT 1 FROM ir_model WHERE model = 'helpdesk.ai.prompt.template'")
    if not cr.fetchone():
        _logger.info("No helpdesk.ai.prompt.template model found, skipping migration")
        return
    
    # Check if the new model exists
    cr.execute("SELECT 1 FROM ir_model WHERE model = 'openwebui.prompt.template'")
    if not cr.fetchone():
        _logger.warning("openwebui.prompt.template model not found, cannot migrate")
        return
    
    # Get all templates from the old model
    cr.execute("""
        SELECT id, name, content, is_default, active, sequence 
        FROM helpdesk_ai_prompt_template
    """)
    old_templates = cr.fetchall()
    
    if not old_templates:
        _logger.info("No templates found in helpdesk.ai.prompt.template, skipping migration")
        return
    
    _logger.info(f"Found {len(old_templates)} templates to migrate")
    
    # For each template, create a corresponding record in the new model
    for template_id, name, content, is_default, active, sequence in old_templates:
        # Check if a template with the same name already exists in the new model
        cr.execute("""
            SELECT id FROM openwebui_prompt_template 
            WHERE name = %s AND template_type = 'helpdesk'
        """, (name,))
        existing = cr.fetchone()
        
        if existing:
            _logger.info(f"Template '{name}' already exists in openwebui.prompt.template, updating")
            cr.execute("""
                UPDATE openwebui_prompt_template 
                SET content = %s, is_default = %s, active = %s, sequence = %s
                WHERE id = %s
            """, (content, is_default, active, sequence, existing[0]))
        else:
            _logger.info(f"Creating new template '{name}' in openwebui.prompt.template")
            cr.execute("""
                INSERT INTO openwebui_prompt_template 
                (name, content, is_default, active, sequence, template_type, create_date, write_date)
                VALUES (%s, %s, %s, %s, %s, 'helpdesk', now(), now())
            """, (name, content, is_default, active, sequence))
    
    # Update system parameters that reference the old model
    cr.execute("""
        SELECT key, value FROM ir_config_parameter
        WHERE key LIKE 'helpdesk_sale_order_ai.%_prompt_template_id'
    """)
    params = cr.fetchall()
    
    for key, value in params:
        if value and value.isdigit():
            # Get the name of the template
            cr.execute("""
                SELECT name FROM helpdesk_ai_prompt_template
                WHERE id = %s
            """, (int(value),))
            template_name = cr.fetchone()
            
            if template_name:
                # Find the corresponding template in the new model
                cr.execute("""
                    SELECT id FROM openwebui_prompt_template
                    WHERE name = %s AND template_type = 'helpdesk'
                """, (template_name[0],))
                new_template_id = cr.fetchone()
                
                if new_template_id:
                    new_key = key.replace('helpdesk_sale_order_ai', 'openwebui_connector')
                    _logger.info(f"Updating system parameter {key} to {new_key} with value {new_template_id[0]}")
                    
                    # Check if the new parameter already exists
                    cr.execute("""
                        SELECT id FROM ir_config_parameter
                        WHERE key = %s
                    """, (new_key,))
                    existing_param = cr.fetchone()
                    
                    if existing_param:
                        cr.execute("""
                            UPDATE ir_config_parameter
                            SET value = %s
                            WHERE id = %s
                        """, (str(new_template_id[0]), existing_param[0]))
                    else:
                        cr.execute("""
                            INSERT INTO ir_config_parameter (key, value)
                            VALUES (%s, %s)
                        """, (new_key, str(new_template_id[0])))
    
    _logger.info("Migration of AI prompt templates completed")
