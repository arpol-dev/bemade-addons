# -*- coding: utf-8 -*-
from odoo import models, fields, api


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
            
        # Otherwise, check global setting
        param_value = self.env['ir.config_parameter'].sudo().get_param('helpdesk_sale_order_ai.use_ai_sale_orders', 'False')
        return param_value.lower() == 'true' if isinstance(param_value, str) else bool(param_value)
    
    def _get_ai_prompt_template(self):
        """Get the AI prompt template to use for this team"""
        self.ensure_one()
        
        # Ensure template model is initialized
        self.env['openwebui.prompt.template']._ensure_default_template('helpdesk')
        
        # If team has a specific template, use it
        if self.ai_prompt_template_id and self.ai_prompt_template_id.exists():
            return self.ai_prompt_template_id.content
            
        # Otherwise, get the global default template
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
        
        if template_id:
            try:
                template = self.env['openwebui.prompt.template'].browse(int(template_id))
                if template.exists():
                    return template.content
            except (ValueError, TypeError):
                pass
                
        # Fallback to default template
        default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
        return default_template.content if default_template else """
            Based on the following helpdesk ticket description, identify products and services that should be included in a sales order:

            Ticket Description: {description}
            Customer: {customer}

            Please provide a list of products/services with quantities and descriptions in the following format:
            Product/Service Name | Quantity | Description
        """
