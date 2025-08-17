from . import models
from . import wizards

from odoo import api, SUPERUSER_ID

def post_init_hook(env):
    """Post-install hook to set up customer-specific configuration."""
    # Set default configuration parameters for customer instances
    ICP = env['ir.config_parameter']
    
    # Ensure the parameters exist with default values
    defaults = {
        'customer.sync.default_url': 'https://odoo.bemade.org',
        'customer.sync.default_database': 'bemade',
        'customer.sync.default_username': 'customer_sync',
        'customer.sync.default_connection_type': 'odoorpc',
        'bemade.sync.default_timeout': '30',
        'bemade.sync.default_retry_count': '3',
        'bemade.sync.default_retry_delay': '5',
    }
    
    for key, value in defaults.items():
        if not ICP.get_param(key):
            ICP.set_param(key, value)
