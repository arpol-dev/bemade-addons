# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AIOpenWebUIPromptTemplate(models.AbstractModel):
    """
    Abstract model to provide a bridge between the old ai.openwebui.prompt.template model
    and the new openwebui.prompt.template model from the openwebui_base module.
    
    This ensures backward compatibility while leveraging the new centralized infrastructure.
    """
    _name = "ai.openwebui.prompt.template"
    _description = "OpenWebUI Prompt Template Bridge"
    
    @api.model
    def _ensure_default_template(self, template_type='helpdesk'):
        """Ensure that a default template exists for the given type"""
        return self.env['openwebui.prompt.template']._ensure_default_template(template_type)
    
    @api.model
    def get_default_template(self, template_type='helpdesk'):
        """Get the default template for the given type"""
        return self.env['openwebui.prompt.template'].get_default_template(template_type)
