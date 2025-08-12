from . import models
from . import utils
import logging

_logger = logging.getLogger(__name__)

# Apply patching on module import
from .models.sync_observer import patch_models
_logger.info("Applying sync observer patches on module import")
patch_models()

def post_init_hook(env=None, registry=None):
    """Post-initialization hook.
    
    This function is called after the module is installed to initialize
    the model patching for synchronization.
    
    In Odoo 17/18, this function is called with (env), while in earlier versions
    it's called with (cr, registry). We handle both cases for compatibility.
    """
    _logger.info("Applying sync observer patches in post_init_hook")
    from .models.sync_observer import patch_models
    patch_models()
