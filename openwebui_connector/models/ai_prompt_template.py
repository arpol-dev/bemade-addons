# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AIPromptTemplate(models.Model):
    _name = 'openwebui.prompt.template'
    _description = 'AI Prompt Template'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    content = fields.Text(
        string='Template Content', 
        required=True,
        help='Template for the prompt sent to the AI. Use placeholders like {description}, {customer}, etc.'
    )
    template_type = fields.Selection([
        ('helpdesk', 'Helpdesk'),
        ('general', 'General'),
    ], string='Template Type', default='helpdesk', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    is_default = fields.Boolean(string='Default Template', default=False)

    @api.model
    def _ensure_default_template(self, template_type='helpdesk'):
        """Ensure that at least one default template exists for the given type"""
        _logger.info(f"Ensuring default template exists for type: {template_type}")
        try:
            default_template = self.search([('template_type', '=', template_type), ('is_default', '=', True)], limit=1)
            _logger.info(f"Found existing default template: {bool(default_template)}")
            
            if not default_template:
                _logger.info("No default template found, creating one")
                # Create a default template
                default_content = self._get_default_template_content(template_type)
                default_name = f"Default {template_type.capitalize()} Template"
                
                try:
                    _logger.info(f"Creating default template with name: {default_name}")
                    default_template = self.create({
                        'name': default_name,
                        'template_type': template_type,
                        'content': default_content,
                        'is_default': True,
                    })
                    _logger.info(f"Default template created with ID: {default_template.id}")
                    
                    # Set the default template ID in system parameters
                    if template_type == 'helpdesk':
                        _logger.info("Setting default template ID in system parameters")
                        param_name = 'helpdesk_sale_order_ai.default_prompt_template_id'
                        param_value = str(default_template.id)
                        _logger.info(f"Setting parameter {param_name} = {param_value}")
                        
                        self.env['ir.config_parameter'].sudo().set_param(
                            param_name, param_value
                        )
                except Exception as e:
                    _logger.error(f"Error creating default template: {e}", exc_info=True)
                    _logger.error(f"Template data: name={default_name}, type={template_type}, content_length={len(default_content) if default_content else 0}")
            
            return default_template
        except Exception as e:
            _logger.error(f"Unexpected error in _ensure_default_template: {e}", exc_info=True)
            return False

    @api.model
    def _get_default_template_content(self, template_type):
        """Get the default content for a template type"""
        if template_type == 'helpdesk':
            return """Based on the following helpdesk ticket information, create a complete sales order that accurately reflects the client's requirements.

Ticket Information: {description}
Customer: {customer}
Subject: {subject}

Analyze all information including ticket description, chatter messages, and attachments to create a comprehensive sales order that includes ALL items the client has requested.

Please provide a detailed list of products and services with exact quantities, specifications, and any relevant details mentioned by the client. Include part numbers when available.

Format your response as follows:
- [Quantity]x [Product Name] [Part Number if available]: [Specifications/Details]

For example:
- 2x Air Compressor Filter P-AC500: 5 micron, high-efficiency as specified in technical document
- 1x Preventive Maintenance Service: Annual service package including parts and labor
- 3x Pneumatic Valves PV-230: 3/4" NPT connection, 150 PSI max pressure

If the client has provided pricing expectations or budget constraints, include this information. If specific delivery timeframes are mentioned, note these as well.
"""
        elif template_type == 'general':
            return """You are a helpful AI assistant. Please analyze the following content and provide a concise and helpful response:

{content}
"""
        else:
            return """Please provide a prompt template for this type of content."""

    def set_as_default(self):
        """Set this template as the default for its type"""
        # First, unset any existing default templates of the same type
        other_defaults = self.search([
            ('id', '!=', self.id),
            ('template_type', '=', self.template_type),
            ('is_default', '=', True)
        ])
        other_defaults.write({'is_default': False})
        
        # Set this template as default
        self.is_default = True
        
        # Update the system parameter if this is a helpdesk template
        if self.template_type == 'helpdesk':
            self.env['ir.config_parameter'].sudo().set_param(
                'helpdesk_sale_order_ai.default_prompt_template_id', 
                str(self.id)
            )
        
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle default templates"""
        records = super(AIPromptTemplate, self).create(vals_list)
        
        # Group templates by type
        templates_by_type = {}
        for record in records:
            if record.is_default:
                if record.template_type not in templates_by_type:
                    templates_by_type[record.template_type] = []
                templates_by_type[record.template_type].append(record.id)
        
        # For each type with new default templates, unset default flag on others of the same type
        for template_type, template_ids in templates_by_type.items():
            self.search([
                ('id', 'not in', template_ids), 
                ('is_default', '=', True),
                ('template_type', '=', template_type)
            ]).write({'is_default': False})
            
        return records

    @api.model
    def get_default_template(self, template_type='helpdesk'):
        """Get the default template for the given type"""
        _logger.info(f"Getting default template for type: {template_type}")
        try:
            default_template = self.search([
                ('is_default', '=', True),
                ('template_type', '=', template_type),
                ('active', '=', True),
            ], limit=1)
            
            _logger.info(f"Found default template: {bool(default_template)}")
            
            if not default_template:
                _logger.info("No active default template found, ensuring one exists")
                # Create a default template if none exists
                default_template = self._ensure_default_template(template_type)
                _logger.info(f"Default template after ensure: {bool(default_template)} with ID: {default_template.id if default_template else 'None'}")
            else:
                _logger.info(f"Using existing default template with ID: {default_template.id}")
            
            return default_template
        except Exception as e:
            _logger.error(f"Error in get_default_template: {e}", exc_info=True)
            # Try to create a new template as a fallback
            try:
                _logger.info("Attempting to create a new default template as fallback")
                default_content = self._get_default_template_content(template_type)
                default_name = f"Fallback {template_type.capitalize()} Template"
                
                fallback_template = self.create({
                    'name': default_name,
                    'template_type': template_type,
                    'content': default_content,
                    'is_default': True,
                })
                _logger.info(f"Created fallback template with ID: {fallback_template.id}")
                return fallback_template
            except Exception as e2:
                _logger.error(f"Failed to create fallback template: {e2}", exc_info=True)
                return self.browse()  # Return empty recordset
