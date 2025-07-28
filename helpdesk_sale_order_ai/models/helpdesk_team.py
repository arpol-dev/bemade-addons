# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_ai_sale_orders = fields.Boolean(
        string='Use AI for Sale Orders',
        help='If checked, the system will use AI to automatically generate sale orders from ticket descriptions for this team. This overrides the global setting.',
        default=False,
    )
    
    ai_prompt_template_id = fields.Many2one(
        'openwebui.prompt.template',
        domain="[('template_type', '=', 'helpdesk')]",
        string='AI Prompt Template',
        help='Template for the prompt sent to the AI. If empty, the global template will be used.',
    )
    
    def _get_use_ai_sale_orders(self):
        """Get whether to use AI sale orders, considering both team and global settings"""
        self.ensure_one()
        # If team has specific setting, use that
        if self.use_ai_sale_orders:
            return True
            
        # Otherwise, check global setting (default to True)
        param_value = self.env['ir.config_parameter'].sudo().get_param('helpdesk_sale_order_ai.use_ai_sale_orders', 'True')
        return param_value.lower() == 'true' if isinstance(param_value, str) else bool(param_value)
    
    def _get_ai_prompt_template(self):
        """Get the AI prompt template to use for this team"""
        self.ensure_one()
        
        try:
            # Ensure template model is initialized
            self.env['openwebui.prompt.template']._ensure_default_template('helpdesk')
            
            # If team has a specific template, use it
            if self.ai_prompt_template_id and self.ai_prompt_template_id.exists():
                _logger.info(f"Using team-specific prompt template: {self.ai_prompt_template_id.name}")
                return self.ai_prompt_template_id.content
                
            # Otherwise, get the global default template
            default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
            if default_template:
                _logger.info(f"Using default helpdesk prompt template: {default_template.name}")
                return default_template.content
        except Exception as e:
            _logger.error(f"Error retrieving prompt template: {str(e)}")
            
        # Fallback to hardcoded template if all else fails
        _logger.warning("Using fallback hardcoded prompt template")
        return """
            Based on the following helpdesk ticket description, identify products and services that should be included in a sales order:

            Ticket Description: {description}
            Chatter Messages: {chatter_messages}
            Attachments: {attachments_info}
            Attachment Contents: {attachment_contents}

            Please provide a list of products/services with quantities and descriptions in the following format:
            Product/Service Name | Quantity | Description
        """
