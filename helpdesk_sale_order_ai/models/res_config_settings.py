# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Inherit the fields from openwebui_base module
    # These fields are already defined in the openwebui_base module
    
    # Add a field to select the prompt template directly
    helpdesk_ai_prompt_template_id = fields.Many2one(
        'openwebui.prompt.template',
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
    
    @api.model
    def get_prompt_template(self):
        """Get the prompt template content from the selected template or default"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
        
        if template_id:
            try:
                # Make sure the template model exists first
                self.env['ai.openwebui.prompt.template']._ensure_default_template('helpdesk')
                # The template_id is already an integer in the database now
                template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                template = self.env['ai.openwebui.prompt.template'].browse(template_id_int)
                if template.exists():
                    return template.content
            except (ValueError, TypeError) as e:
                _logger.error(f"Error retrieving prompt template: {e}")
                pass
                
        # Fallback to default template
        default_template = self.env['ai.openwebui.prompt.template'].get_default_template('helpdesk')
        return default_template.content if default_template else ""
