# -*- coding: utf-8 -*-

from . import models
from . import views

def post_init_hook(cr, registry=None):
    """Initialize default AI prompt template after module installation
    
    Note: This function can be called with either one argument (env) or two arguments (cr, registry)
    to accommodate different Odoo hook calling conventions.
    """
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info("=== START: post_init_hook ====")
    
    try:
        from odoo import api, SUPERUSER_ID
        
        # Handle different calling conventions
        if hasattr(cr, 'env'):  # cr is actually an env
            env = cr
            _logger.info("Using provided environment")
        elif registry:  # We have both cr and registry
            env = api.Environment(cr, SUPERUSER_ID, {})
            _logger.info("Created environment from cursor and registry")
        else:
            _logger.warning("Cannot create environment, skipping template creation")
            return
            
        _logger.info("Calling _ensure_default_template")
        # Use our bridge model which will call the correct underlying model
        env['ai.openwebui.prompt.template']._ensure_default_template('helpdesk')
        _logger.info("Default template ensured successfully")
        _logger.info("=== END: post_init_hook ====")
    except Exception as e:
        _logger.error(f"ERROR in post_init_hook: {str(e)}")
        _logger.exception("Exception traceback:")
        # Don't raise the exception to prevent installation failure
        return
