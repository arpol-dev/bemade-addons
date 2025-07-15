# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AIPromptTemplate(models.Model):
    _name = 'helpdesk.ai.prompt.template'
    _description = 'AI Prompt Template'
    _rec_name = 'name'
    _order = 'sequence, id'

    name = fields.Char(
        string='Name',
        required=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    is_default = fields.Boolean(
        string='Is Default',
        default=False,
    )
    content = fields.Text(
        string='Template Content',
        required=True,
        help='Template for the prompt sent to the AI. Use placeholders like {description}, {customer}, etc.',
    )

    @api.model
    def _ensure_default_template(self):
        """Ensure there's at least one default template"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== START: _ensure_default_template ====")
        
        try:
            _logger.info("Searching for default template")
            default_template = self.search([('is_default', '=', True)], limit=1)
            _logger.info(f"Default template search result: {default_template}")
            
            if not default_template:
                _logger.info("No default template found, creating one")
                # Create a default template if none exists
                default_content = """Based on the following helpdesk ticket description, identify products and services that should be included in a sales order:

Ticket Description: {description}
Customer: {customer}

Please provide a list of products/services with quantities and descriptions in the following format:
Product/Service Name | Quantity | Description
"""
                _logger.info("Creating default template")
                new_template = self.create({
                    'name': 'Default Template',
                    'content': default_content,
                    'is_default': True,
                })
                _logger.info(f"Created default template: {new_template}")
            else:
                _logger.info(f"Found existing default template: {default_template.name}")
                
            _logger.info("=== END: _ensure_default_template ====")
            return True
        except Exception as e:
            _logger.error(f"ERROR in _ensure_default_template: {str(e)}")
            _logger.exception("Exception traceback:")
            raise
        
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle default templates"""
        records = super(AIPromptTemplate, self).create(vals_list)
        # If any new template is set as default, unset default flag on others
        default_templates = records.filtered(lambda r: r.is_default)
        if default_templates:
            self.search([('id', 'not in', default_templates.ids), ('is_default', '=', True)]).write({'is_default': False})
        return records

    @api.model
    def get_default_template(self):
        """Get the default template"""
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("=== START: get_default_template ====")
        
        try:
            _logger.info("Searching for default template")
            default_template = self.search([('is_default', '=', True)], limit=1)
            _logger.info(f"Default template search result: {default_template}")
            
            if not default_template:
                _logger.info("No default template found, ensuring one exists")
                self._ensure_default_template()
                default_template = self.search([('is_default', '=', True)], limit=1)
                _logger.info(f"Default template after ensure: {default_template}")
                
            _logger.info("=== END: get_default_template ====")
            return default_template
        except Exception as e:
            _logger.error(f"ERROR in get_default_template: {str(e)}")
            _logger.exception("Exception traceback:")
            return self.browse()

    def set_as_default(self):
        """Set this template as the default"""
        if self:
            # Clear default flag on all other templates
            self.search([('id', '!=', self.id)]).write({'is_default': False})
            # Set this template as default
            self.write({'is_default': True})
        return True
