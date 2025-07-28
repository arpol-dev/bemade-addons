# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import requests
import json

_logger = logging.getLogger(__name__)

class AIOpenWebUIClient(models.AbstractModel):
    """
    Abstract model to provide a bridge between the helpdesk_sale_order_ai module
    and the openwebui_base module.
    
    This ensures proper integration with the OpenWebUI API using configuration
    from the settings.
    """
    _name = "helpdesk_sale_order_ai.openwebui.client"
    _description = "OpenWebUI Client"
    
    @api.model
    def chat_completion(self, messages, model=None, **kwargs):
        """
        Send a chat completion request to the OpenWebUI API
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: The model to use for the completion (default: anthropic.claude-3-7-sonnet-latest)
            **kwargs: Additional parameters to pass to the OpenWebUI client
            
        Returns:
            The response from the OpenWebUI API
        """
        # Check if openwebui_base module is installed
        module_obj = self.env['ir.module.module']
        openwebui_base_module = module_obj.search([('name', '=', 'openwebui_base'), ('state', '=', 'installed')])
        
        if not openwebui_base_module:
            _logger.error("The openwebui_base module is not installed. Cannot use AI features.")
            return False
        
        try:
            # Get configuration from settings
            config = self.env['ir.config_parameter'].sudo()
            company = self.env.company
            
            # Get provider configuration
            provider = company.openwebui_provider_id
            if not provider:
                _logger.error("No OpenWebUI provider configured for this company")
                return False
                
            # Get API key and base URL from provider
            api_key = provider.api_key
            base_url = provider.base_url
            
            if not api_key or not base_url:
                _logger.error("Missing API key or base URL in OpenWebUI provider configuration")
                return False
            
            # Get model from company settings or use provided model or default
            if not model and company.openwebui_default_model_id:
                model = company.openwebui_default_model_id.technical_name
                
            _logger.info(f"Using OpenWebUI API with model={model} and {len(messages)} messages")
            
            # Log first few characters of the prompt for debugging
            if messages and len(messages) > 0:
                first_content = messages[0].get('content', '')[:100]
                _logger.info(f"First message content (truncated): {first_content}...")
            
            # Prepare the request
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            data = {
                'model': model,
                'messages': messages,
                **kwargs
            }
            
            # Make the API call
            endpoint = f"{base_url.rstrip('/')}/chat/completions"
            _logger.info(f"Sending request to {endpoint}")
            
            response = requests.post(
                endpoint,
                headers=headers,
                json=data,
                timeout=60  # Reasonable timeout for AI responses
            )
            
            # Check for successful response
            response.raise_for_status()
            result = response.json()
            
            # Log response summary
            if result:
                _logger.info(f"Received response from OpenWebUI API: {str(result)[:200]}...")
            else:
                _logger.warning("Received empty response from OpenWebUI API")
                
            return result
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"API request error in chat_completion: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error in chat_completion: {str(e)}")
            return False
        except Exception as e:
            _logger.error(f"Unexpected error in chat_completion: {str(e)}")
            return False
