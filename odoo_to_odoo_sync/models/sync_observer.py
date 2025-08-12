# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Model Change Observer System.

This module implements the observer pattern to detect changes in Odoo models
and trigger synchronization operations. It hooks into the create, write, and
unlink methods of models to detect changes and queue them for synchronization.
"""

import logging
from functools import wraps

from odoo import api, models, tools

_logger = logging.getLogger(__name__)

# Global registry to avoid duplicate patching
PATCHED_MODELS = set()

class SyncObserver:
    """Observer class for model changes.
    
    This class provides methods to patch standard Odoo methods (create, write, unlink)
    to detect changes and trigger synchronization operations.
    """
    
    @staticmethod
    def _observe_create(original_method):
        """Observe the create method of a model.
        
        Args:
            original_method: The original create method to wrap
            
        Returns:
            function: Wrapped create method with synchronization logic
        """
        @wraps(original_method)
        def wrapper(self, vals):
            # Call the original method first
            result = original_method(self, vals)
            
            # Debug log
            _logger.debug("[SYNC DEBUG] Create called for model: %s", self._name)
            
            # Check if this model is configured for synchronization
            # Skip synchronization for models in the odoo_to_odoo_sync module to prevent recursive loops
            if not self.env.context.get('no_sync') and not self._name.startswith('odoo.sync.'):
                try:
                    _logger.debug("[SYNC DEBUG] Checking sync model for %s", self._name)
                    sync_model = self.env['odoo.sync.model'].sudo().search([
                        ('model_id.model', '=', self._name),
                        ('active', '=', True)
                    ])
                    
                    _logger.debug("[SYNC DEBUG] Found sync models: %s", sync_model)
                    
                    if sync_model:
                        # Get the sync manager
                        sync_manager = self.env['odoo.sync.manager'].sudo()
                        
                        # Queue the synchronization (Notify Change -> Create SyncRecord in sequence diagram)
                        for record in result:
                            _logger.info("[SYNC OBSERVER] Notify Change: create for record %s (model %s)", record.id, self._name)
                            sync_manager._queue_sync(record, 'create')
                    else:
                        _logger.info("[SYNC DEBUG] No sync model found for %s", self._name)
                            
                except Exception as e:
                    _logger.error("Error in sync observer (create): %s", str(e))
            
            return result
        
        return wrapper
    
    @staticmethod
    def _observe_write(original_method):
        """Observe the write method of a model.
        
        Args:
            original_method: The original write method to wrap
            
        Returns:
            function: Wrapped write method with synchronization logic
        """
        @wraps(original_method)
        def wrapper(self, vals):
            # Call the original method first
            result = original_method(self, vals)
            
            # Check if this model is configured for synchronization
            if not self.env.context.get('no_sync') and not self._name.startswith('odoo.sync.'):
                try:
                    sync_model = self.env['odoo.sync.model'].sudo().search([
                        ('model_id.model', '=', self._name),
                        ('active', '=', True)
                    ])
                    
                    if sync_model:
                        # Get the sync manager
                        sync_manager = self.env['odoo.sync.manager'].sudo()
                        
                        # Queue the synchronization for each record
                        for record in self:
                            _logger.info("[SYNC OBSERVER] Notify Change: write for record %s (model %s)", record.id, self._name)
                            sync_manager._queue_sync(record, 'write', vals.keys())
                            
                except Exception as e:
                    _logger.error("Error in sync observer (write): %s", str(e))
            
            return result
        
        return wrapper
    
    @staticmethod
    def _observe_unlink(original_method):
        """Observe the unlink method of a model.
        
        Args:
            original_method: The original unlink method to wrap
            
        Returns:
            function: Wrapped unlink method with synchronization logic
        """
        @wraps(original_method)
        def wrapper(self):
            # Check if this model is configured for synchronization
            if not self.env.context.get('no_sync') and not self._name.startswith('odoo.sync.'):
                try:
                    sync_model = self.env['odoo.sync.model'].sudo().search([
                        ('model_id.model', '=', self._name),
                        ('active', '=', True)
                    ])
                    
                    if sync_model:
                        # Get the sync manager
                        sync_manager = self.env['odoo.sync.manager'].sudo()
                        
                        # Queue the synchronization for each record before deletion
                        for record in self:
                            sync_manager._queue_sync(record, 'unlink')
                            
                except Exception as e:
                    _logger.error("Error in sync observer (unlink): %s", str(e))
            
            # Call the original method after queueing
            return original_method(self)
        
        return wrapper

def patch_models():
    """Patch all models with synchronization observers.
    
    This function is called during module initialization to patch
    the create, write, and unlink methods of the BaseModel class.
    """
    if models.BaseModel in PATCHED_MODELS:
        return
    
    # Patch the methods
    models.BaseModel.create = SyncObserver._observe_create(models.BaseModel.create)
    models.BaseModel.write = SyncObserver._observe_write(models.BaseModel.write)
    models.BaseModel.unlink = SyncObserver._observe_unlink(models.BaseModel.unlink)
    
    # Mark as patched
    PATCHED_MODELS.add(models.BaseModel)
    
    _logger.info("Model synchronization observers installed")
