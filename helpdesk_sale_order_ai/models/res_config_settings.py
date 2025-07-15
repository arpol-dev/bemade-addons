# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # We no longer need to define the fields here as they are now defined in the openai_connector module
    # This ensures that the settings are always in sync between the two modules
    
    # Override the model field to use our selection method
    openai_model = fields.Selection(
        selection='_get_openwebui_models',
        string='AI Model',
        help='Model to use for AI API calls',
        default='anthropic.claude-3-7-sonnet-latest',
        config_parameter='openai.model',
    )
    
    # Add a field to select the prompt template directly
    # In Odoo 18, we need to ensure this field is properly defined
    helpdesk_ai_prompt_template_id = fields.Many2one(
        'openwebui.prompt.template',
        domain="[('template_type', '=', 'helpdesk')]",
        string='Default AI Prompt Template',
        help='Default template for the prompt sent to the AI.',
        ondelete='set null',  # This helps avoid constraint errors
    )
    
    @api.model
    def get_values(self):
        """Get values for the settings form"""
        res = super(ResConfigSettings, self).get_values()
        
        # Get the template ID from the system parameter
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
        
        if template_id:
            try:
                template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                res['helpdesk_ai_prompt_template_id'] = template_id_int
            except (ValueError, TypeError):
                _logger.error(f"Invalid template ID in system parameter: {template_id}")
        
        return res
    
    def set_values(self):
        """Set values from the settings form"""
        super(ResConfigSettings, self).set_values()
        
        # Save the template ID to the system parameter
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        if self.helpdesk_ai_prompt_template_id:
            IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(self.helpdesk_ai_prompt_template_id.id))
        else:
            # If no template is selected, ensure there's a default one
            self._set_default_values()
    
    @api.model
    def _get_openwebui_models(self):
        """Get available models from OpenWebUI API"""
        try:
            client = self.env['openwebui.client']
            models = client.get_available_models()
            return models
        except Exception as e:
            _logger.error(f"Error fetching OpenWebUI models: {e}")
            # Return default model on error
            default_model = 'anthropic.claude-3-7-sonnet-latest'
            return [(default_model, default_model)]
    
    @api.model
    def _set_default_values(self):
        """Set default values for configuration parameters"""
        # Ensure there's a default template
        template_model = self.env['openwebui.prompt.template']
        template_model._ensure_default_template()
        default_template = template_model.get_default_template()
        
        # Set the default template ID in config parameters if not set
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        default_template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id')
        if not default_template_id and default_template:
            # Store as string to ensure compatibility with the OpenAI connector module
            IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
    
    @api.model
    def get_prompt_template(self):
        """Get the prompt template content from the selected template or default"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
        
        if template_id:
            try:
                # Make sure the template model exists first
                self.env['openwebui.prompt.template']._ensure_default_template('helpdesk')
                # The template_id is already an integer in the database now
                template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                template = self.env['openwebui.prompt.template'].browse(template_id_int)
                if template.exists():
                    return template.content
            except (ValueError, TypeError) as e:
                _logger.error(f"Error retrieving prompt template: {e}")
                pass
                
        # Fallback to default template
        default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
        return default_template.content if default_template else ""
