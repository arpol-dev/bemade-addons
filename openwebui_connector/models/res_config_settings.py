# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # AI API Configuration (unified for all AI services)
    openai_api_key = fields.Char(
        string='AI API Key',
        help='API key for AI services (OpenAI, OpenWebUI, Claude)',
        config_parameter='openwebui.api_key',
    )
    
    openai_base_url = fields.Char(
        string='AI Base URL',
        help='Base URL for AI API',
        default='https://api.openai.com/v1',  # Default OpenAI endpoint
        config_parameter='openwebui.base_url',
    )
    
    # Use Selection field with dynamic options from OpenWebUI client
    openai_model = fields.Selection(
        selection='_get_openwebui_models',
        string='AI Model',
        help='Model to use for AI API calls',
        default='anthropic.claude-3-7-sonnet-latest',
        config_parameter='openwebui.model',
    )
    
    # Helpdesk AI fields
    helpdesk_use_ai_sale_orders = fields.Boolean(
        string='Use AI for Sale Orders',
        help='If checked, the system will use AI to automatically generate sale orders from helpdesk ticket descriptions.',
        config_parameter='helpdesk_sale_order_ai.use_ai_sale_orders',
    )
    
    # Add a field to select the prompt template directly
    # In Odoo 18, we need to ensure this field is properly defined
    ai_prompt_template_id = fields.Integer(
        string='Default AI Prompt Template ID',
        help='Default template ID for the prompt sent to the AI.',
        compute='_compute_ai_prompt_template_id',
        inverse='_inverse_ai_prompt_template_id',
        store=False,  # Don't store this field to avoid constraint issues
    )
    
    # Actual relation field for the template, but not stored in database
    ai_prompt_template_relation = fields.Many2one(
        'openwebui.prompt.template',
        string='Default AI Prompt Template',
        help='Default template for the prompt sent to the AI.',
        compute='_compute_ai_prompt_template_relation',
        domain="[('template_type', '=', 'helpdesk')]",
        store=False,  # Don't store this field to avoid constraint issues
    )
    
    # Display field for backward compatibility
    helpdesk_ai_template_display = fields.Char(
        string='Default AI Prompt Template',
        help='Default template for the prompt sent to the AI.',
        compute='_compute_helpdesk_ai_template_display',
        readonly=True,
        store=False,  # Important: don't store this field in the database
    )
    
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
    
    def _compute_ai_prompt_template_id(self):
        """Compute the template ID from system parameter"""
        for record in self:
            IrConfigParam = self.env['ir.config_parameter'].sudo()
            template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
            
            if template_id:
                try:
                    # Convert to integer if it's a string
                    template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                    record.ai_prompt_template_id = template_id_int
                except (ValueError, TypeError):
                    record.ai_prompt_template_id = False
            else:
                record.ai_prompt_template_id = False
    
    def _inverse_ai_prompt_template_id(self):
        """Save the template ID to system parameter"""
        for record in self:
            IrConfigParam = self.env['ir.config_parameter'].sudo()
            if record.ai_prompt_template_id:
                IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(record.ai_prompt_template_id))
            else:
                # Try to get a default template
                default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
                if default_template:
                    IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
    
    def _compute_ai_prompt_template_relation(self):
        """Compute the template relation from the ID"""
        for record in self:
            if record.ai_prompt_template_id:
                template = self.env['openwebui.prompt.template'].browse(record.ai_prompt_template_id)
                if template.exists():
                    record.ai_prompt_template_relation = template.id
                else:
                    record.ai_prompt_template_relation = False
            else:
                record.ai_prompt_template_relation = False
    
    @api.depends('ai_prompt_template_relation')
    def _compute_helpdesk_ai_template_display(self):
        """Compute the template name from the selected template"""
        for record in self:
            if record.ai_prompt_template_relation:
                record.helpdesk_ai_template_display = record.ai_prompt_template_relation.name
            else:
                # Try to get from system parameter for backward compatibility
                IrConfigParam = self.env['ir.config_parameter'].sudo()
                template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
                
                if template_id:
                    try:
                        # Convert to integer if it's a string
                        template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                        
                        # Try to find the template in the new model
                        template = self.env['openwebui.prompt.template'].browse(template_id_int)
                        if template.exists():
                            record.helpdesk_ai_template_display = template.name
                        else:
                            record.helpdesk_ai_template_display = f'Template #{template_id} (not found)'
                    except (ValueError, TypeError):
                        record.helpdesk_ai_template_display = f'Template #{template_id} (invalid)'
                else:
                    record.helpdesk_ai_template_display = 'Default Template'
    
    @api.model
    def _set_default_values(self):
        """Set default values for configuration parameters"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        base_url = IrConfigParam.get_param('openwebui.base_url')
        model = IrConfigParam.get_param('openwebui.model')
        
        # Check for old parameters and migrate them
        old_api_key = IrConfigParam.get_param('openai.api_key', False)
        old_base_url = IrConfigParam.get_param('openai.base_url', False)
        old_model = IrConfigParam.get_param('openai.model', False)
        
        # Migrate old parameters to new ones if they exist
        if old_api_key and not IrConfigParam.get_param('openwebui.api_key', False):
            IrConfigParam.set_param('openwebui.api_key', old_api_key)
            
        if old_base_url and not base_url:
            IrConfigParam.set_param('openwebui.base_url', old_base_url)
            
        if old_model and not model:
            IrConfigParam.set_param('openwebui.model', old_model)
        
        # Set defaults if not already set
        if not base_url:
            IrConfigParam.set_param('openwebui.base_url', 'https://api.openai.com/v1')
        
        if not model:
            IrConfigParam.set_param('openwebui.model', 'anthropic.claude-3-7-sonnet-latest')
        
        # Ensure there's a default template
        template_model = self.env['openwebui.prompt.template']
        template_model._ensure_default_template('helpdesk')
        default_template = template_model.get_default_template('helpdesk')
        
        # Set the default template ID in config parameters if not set
        default_template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id')
        if not default_template_id and default_template:
            IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
    
    @api.model
    def create(self, vals_list):
        """Set default values when creating settings"""
        self._set_default_values()
        return super(ResConfigSettings, self).create(vals_list)
    
    def set_values(self):
        """Set values from the settings form"""
        _logger.info("Starting set_values in ResConfigSettings")
        try:
            # First, explicitly save the API key, base URL, and model to ensure they're saved
            # even if there's an error with the template handling
            IrConfigParam = self.env['ir.config_parameter'].sudo()
            
            # Save API key, base URL, and model directly with explicit error handling
            # API Key - most critical setting
            if hasattr(self, 'openai_api_key'):
                _logger.info(f"Saving API key (present: {bool(self.openai_api_key)})")
                # Always set the parameter, even if None or False, to clear previous value if needed
                api_key_value = self.openai_api_key if self.openai_api_key else ''
                IrConfigParam.set_param('openai.api_key', api_key_value)
                # Verify it was saved
                saved_key = IrConfigParam.get_param('openai.api_key', '')
                _logger.info(f"API key saved successfully: {bool(saved_key)}")
            
            # Base URL
            if hasattr(self, 'openai_base_url'):
                _logger.info(f"Saving base URL: {self.openai_base_url}")
                base_url_value = self.openai_base_url if self.openai_base_url else 'https://ai.bemade.org/api'
                IrConfigParam.set_param('openai.base_url', base_url_value)
                # Verify it was saved
                saved_url = IrConfigParam.get_param('openai.base_url', '')
                _logger.info(f"Base URL saved: {saved_url}")
                
            # Model
            if hasattr(self, 'openai_model'):
                _logger.info(f"Saving model: {self.openai_model}")
                model_value = self.openai_model if self.openai_model else 'anthropic.claude-3-7-sonnet-latest'
                IrConfigParam.set_param('openai.model', model_value)
                # Verify it was saved
                saved_model = IrConfigParam.get_param('openai.model', '')
                _logger.info(f"Model saved: {saved_model}")
                
            _logger.info(f"Current settings values: openai_api_key={bool(self.openai_api_key)}, openai_base_url={self.openai_base_url}, openai_model={self.openai_model}")
            _logger.info(f"Template ID: {self.ai_prompt_template_id if self.ai_prompt_template_id else 'None'}")
            
            # Force a commit to ensure parameters are saved to database
            self.env.cr.commit()
            _logger.info("Committed parameter changes to database")
            
            # Now call the super method
            res = super(ResConfigSettings, self).set_values()
            _logger.info("Super set_values completed successfully")
            
            # Handle the template ID - either save the selected one or ensure a default exists
            try:
                if self.ai_prompt_template_id:
                    _logger.info(f"Saving template ID {self.ai_prompt_template_id} to system parameters")
                    IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(self.ai_prompt_template_id))
                else:
                    # If no template is selected, ensure a default one exists and use that
                    _logger.info("No template selected, getting default template")
                    template_model = self.env['openwebui.prompt.template']
                    try:
                        default_template = template_model.get_default_template('helpdesk')
                        if default_template:
                            _logger.info(f"Using default template ID {default_template.id}")
                            IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
                        else:
                            _logger.warning("No default template found")
                    except Exception as e:
                        _logger.error(f"Error getting default template: {e}", exc_info=True)
                        # Continue execution even if there's an error with the template
            except Exception as template_error:
                _logger.error(f"Error handling template: {template_error}", exc_info=True)
                # Continue execution even if there's an error with the template
            
            # Force another commit to ensure all changes are saved
            self.env.cr.commit()
            _logger.info("Final commit completed")
            
            # Double-check that the API key was saved
            final_api_key = IrConfigParam.get_param('openai.api_key', '')
            _logger.info(f"Final API key check - key exists: {bool(final_api_key)}")
            
            _logger.info("set_values completed successfully")
            return res
        except Exception as e:
            _logger.error(f"Error in set_values: {e}", exc_info=True)
            # Try to save API key directly even if there was an error
            try:
                if hasattr(self, 'openai_api_key'):
                    api_key_value = self.openai_api_key if self.openai_api_key else ''
                    self.env['ir.config_parameter'].sudo().set_param('openai.api_key', api_key_value)
                    self.env.cr.commit()  # Force commit to save the key
                    _logger.info("Saved API key directly after error")
            except Exception as key_error:
                _logger.error(f"Failed to save API key after error: {key_error}")
            raise
    
    @api.model
    def get_values(self):
        """Get values for the settings form"""
        res = super(ResConfigSettings, self).get_values()
        
        # Ensure default values are set
        self._set_default_values()
        
        # Get all OpenAI settings from system parameters
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        
        # Get OpenAI API key, base URL, and model
        _logger.info("Retrieving OpenAI settings from system parameters")
        api_key = IrConfigParam.get_param('openai.api_key', False)
        base_url = IrConfigParam.get_param('openai.base_url', 'https://ai.bemade.org/api')
        model = IrConfigParam.get_param('openai.model', 'anthropic.claude-3-7-sonnet-latest')
        
        # Set the values in the result dictionary
        res.update({
            'openai_api_key': api_key,
            'openai_base_url': base_url,
            'openai_model': model,
        })
        
        _logger.info(f"Retrieved settings: API key present: {bool(api_key)}, base_url: {base_url}, model: {model}")
        
        # Get the template ID from the system parameter
        template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
        
        if template_id:
            try:
                template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                # Check if the template exists
                template = self.env['openwebui.prompt.template'].browse(template_id_int)
                if template.exists():
                    res['ai_prompt_template_id'] = template_id_int
                else:
                    # If template doesn't exist, get a default one
                    default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
                    if default_template:
                        res['ai_prompt_template_id'] = default_template.id
                        # Update the system parameter
                        IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
            except (ValueError, TypeError):
                _logger.error(f"Invalid template ID in system parameter: {template_id}")
                # Get a default template
                default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
                if default_template:
                    res['ai_prompt_template_id'] = default_template.id
                    # Update the system parameter
                    IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
        else:
            # No template ID in system parameters, get a default one
            default_template = self.env['openwebui.prompt.template'].get_default_template('helpdesk')
            if default_template:
                res['ai_prompt_template_id'] = default_template.id
                # Update the system parameter
                IrConfigParam.set_param('helpdesk_sale_order_ai.default_prompt_template_id', str(default_template.id))
        
        return res
    
    def action_open_prompt_templates(self):
        """Open the prompt templates management view"""
        self.ensure_one()
        
        return {
            'name': _('AI Prompt Templates'),
            'type': 'ir.actions.act_window',
            'res_model': 'openwebui.prompt.template',
            'view_mode': 'list,form',
        }
    
    @api.model
    def get_prompt_template(self, template_type='helpdesk'):
        """Get the prompt template content from the selected template or default"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        template_id = IrConfigParam.get_param('helpdesk_sale_order_ai.default_prompt_template_id', False)
        
        if template_id:
            try:
                # Make sure the template model exists first
                self.env['openwebui.prompt.template']._ensure_default_template(template_type)
                # The template_id is already an integer in the database now
                template_id_int = int(template_id) if isinstance(template_id, str) else template_id
                template = self.env['openwebui.prompt.template'].browse(template_id_int)
                if template.exists():
                    return template.content
            except (ValueError, TypeError) as e:
                _logger.error(f"Error retrieving prompt template: {e}")
                pass
                
        # Fallback to default template
        default_template = self.env['openwebui.prompt.template'].get_default_template(template_type)
        return default_template.content if default_template else ""
