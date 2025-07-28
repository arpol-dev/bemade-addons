# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class OpenWebUIPromptTemplate(models.Model):
    _name = "openwebui.prompt.template"
    _description = "OpenWebUI Prompt Template"

    name = fields.Char(string="Name", required=True)
    template_type = fields.Selection([
        ('helpdesk', 'Helpdesk'),
        ('general', 'General'),
        ('custom', 'Custom'),
    ], string="Template Type", default='general', required=True)
    content = fields.Text(string="Template Content", required=True)
    is_default = fields.Boolean(string="Is Default", default=False)
    
    @api.model
    def _ensure_default_template(self, template_type='helpdesk'):
        """Ensure that a default template exists for the given type"""
        default_template = self.search([
            ('template_type', '=', template_type),
            ('is_default', '=', True)
        ], limit=1)
        
        if not default_template:
            # Create a default template based on the type
            if template_type == 'helpdesk':
                self.create({
                    'name': 'Default Helpdesk Template',
                    'template_type': 'helpdesk',
                    'content': """You are a helpful assistant analyzing helpdesk tickets to create sales orders.

IMPORTANT: In this system, product names are often formatted as the product reference number in square brackets followed by the product name (for example: [REF123] Widget). You can use the reference code inside the brackets to identify products in the database. If you are unsure, select the product with the highest matching reference code.

Please analyze the following ticket information and extract:

1. Client reference number (e.g., PO-12345, REF-678)
2. Products or services needed with quantities and descriptions
3. Any special requirements or notes
4. Delivery date expectations
5. Payment terms if mentioned

Ticket Information:
{ticket_description}

{ticket_messages}

Please format your response as a structured JSON with the following format:
{
  "sale_order_fields": {
    "client_order_ref": "Reference number if found",
    "commitment_date": "YYYY-MM-DD if found",
    "payment_term_id": "Payment terms if found"
  },
  "order_lines": [
    {
      "product_name": "Product name or description",
      "quantity": 1.0,
      "notes": "Any special instructions for this line"
    }
  ]
}""",
                    'is_default': True
                })
            elif template_type == 'general':
                self.create({
                    'name': 'Default General Template',
                    'template_type': 'general',
                    'content': """You are a helpful assistant. Please provide a detailed and accurate response to the following query:

{query}""",
                    'is_default': True
                })
    
    @api.model
    def get_default_template(self, template_type='helpdesk'):
        """Get the default template for the given type"""
        self._ensure_default_template(template_type)
        return self.search([
            ('template_type', '=', template_type),
            ('is_default', '=', True)
        ], limit=1)
