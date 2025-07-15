# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import json
import requests
from typing import Dict, List, Any, Optional, Tuple

_logger = logging.getLogger(__name__)

class OpenWebUIClient(models.AbstractModel):
    """
    OpenWebUI client for interacting with the OpenWebUI API.
    This is a simplified version of the external OpenWebUI client integrated into Odoo.
    """
    _name = 'openwebui.client'
    _description = 'OpenWebUI Client for AI Services'

    def _get_config(self, raise_if_missing=True):
        """
        Get the OpenWebUI configuration from the system parameters.
        Uses the dedicated openwebui parameters for API key, base URL and model.
        
        Args:
            raise_if_missing: If True, raise an error when API key is missing.
                             If False, return config with empty API key.
        """
        _logger.debug(f"Getting OpenWebUI config (raise_if_missing={raise_if_missing})")
        try:
            # Get the config from the ir.config_parameter
            IrConfigParam = self.env['ir.config_parameter'].sudo()
            
            # Use dedicated OpenWebUI parameters
            api_key = IrConfigParam.get_param('openwebui.api_key', False)
            
            # If OpenWebUI API key is not set, try fallback to OpenAI key
            if not api_key:
                api_key = IrConfigParam.get_param('openai.api_key', False)
                _logger.debug("OpenWebUI API key not found, falling back to OpenAI API key")
            
            _logger.debug(f"Retrieved API key: {'Present' if api_key else 'Missing'}")
            
            # Get base URL from dedicated parameter
            base_url = IrConfigParam.get_param('openwebui.base_url', 'https://ai.bemade.org/api')
            _logger.debug(f"Using base_url: {base_url}")
            
            # Get model from dedicated parameter
            model = IrConfigParam.get_param('openwebui.model', 'anthropic.claude-3-7-sonnet-latest')
            _logger.debug(f"Using model: {model}")
            
            if not api_key and raise_if_missing:
                _logger.error("No API key found in configuration and raise_if_missing=True")
                raise ValueError("No API key found in configuration")
                
            config = {
                'api_key': api_key or '',
                'base_url': base_url,
                'model': model
            }
            _logger.debug("Successfully retrieved OpenWebUI config")
            return config
        except Exception as e:
            _logger.error(f"Error getting OpenWebUI config: {e}", exc_info=True)
            raise

    def get_available_models(self):
        """
        Fetch available models from the OpenWebUI API.
        
        Returns:
            A list of tuples (model_id, model_name) suitable for selection fields
        """
        _logger.info("Starting get_available_models")
        # Define default_model at the beginning to ensure it's always available
        default_model = 'anthropic.claude-3-7-sonnet-latest'
        
        # Create a list with just the default model to ensure it's always available
        models = [(default_model, default_model)]
        
        try:
            # Get config without raising exception if API key is missing
            config = self._get_config(raise_if_missing=False)
            
            # Update default_model with configured value and ensure it's in the list
            if 'model' in config and config['model']:
                default_model = config['model']
                # Clear the list and add the current default model
                models = [(default_model, default_model)]
            
            _logger.info(f"Default model: {default_model}")
            
            # If no API key is set, just return the current model
            if not config.get('api_key'):
                _logger.warning("No API key configured, only showing current model")
                return models
            
            # Add some common models that we know work with OpenWebUI
            # This ensures we have a good selection even if the API call fails
            common_models = [
                ('anthropic.claude-3-7-sonnet-latest', 'Claude 3.7 Sonnet'),
                ('anthropic.claude-3-5-sonnet-20240620', 'Claude 3.5 Sonnet'),
                ('anthropic.claude-3-opus-20240229', 'Claude 3 Opus'),
                ('gpt-4o', 'GPT-4o'),
                ('gpt-4-turbo', 'GPT-4 Turbo'),
                ('gpt-3.5-turbo', 'GPT-3.5 Turbo')
            ]
            
            # Add common models to our list, but keep the default model first
            for model_id, model_name in common_models:
                if model_id != default_model:  # Avoid duplicates
                    models.append((model_id, model_name))
            
            # Remove trailing slash if present in base_url
            base_url = config.get('base_url', 'https://ai.bemade.org/api')
            if isinstance(base_url, str) and base_url.endswith('/'):
                base_url = base_url[:-1]
            _logger.info(f"Using base URL: {base_url}")
                
            # Check if base_url already contains '/api' to avoid duplicates
            if '/api' in base_url:
                endpoints = [
                    '/v1/models',
                    '/models',
                    '/chat/models',
                    '/v1/chat/models'
                ]
            else:
                endpoints = [
                    '/v1/models',
                    '/models',
                    '/chat/models',
                    '/api/models',
                    '/api/v1/models',
                    '/api/chat/models'
                ]
            _logger.debug(f"Will try these endpoints: {endpoints}")
            
            # Set up authentication headers
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            }
            _logger.debug("Authentication headers set up")
            
            # Try a simple connection test first with a short timeout
            try:
                _logger.info(f"Testing connection to base URL: {base_url}")
                test_response = requests.get(base_url, timeout=3)
                _logger.info(f"Base API connection test: {test_response.status_code}")
                if test_response.status_code >= 400:
                    _logger.warning(f"Base URL returned error status: {test_response.status_code}")
                    return models  # Return our predefined models
            except Exception as e:
                _logger.warning(f"Could not connect to base API URL: {str(e)}")
                # Return our predefined models if we can't connect
                _logger.info("Returning predefined models due to connection error")
                return models
            
            # Try each endpoint with a short timeout
            _logger.info("Starting to try each endpoint for models")
            success = False
            
            for endpoint in endpoints:
                url = f"{base_url}{endpoint}"
                _logger.info(f"Trying endpoint: {url}")
                
                try:
                    _logger.debug(f"Making request to {url} with timeout=5")
                    response = requests.get(url, headers=headers, timeout=5)
                    _logger.info(f"Response status code: {response.status_code}")
                    
                    if response.status_code != 200:
                        _logger.info(f"Endpoint {endpoint} returned non-200 status code: {response.status_code}")
                        continue
                    
                    # Check if response is empty
                    if not response.text or response.text.strip() == '':
                        _logger.warning(f"Empty response from {url}")
                        continue
                    
                    # Try to parse the response as JSON
                    try:
                        _logger.debug("Parsing response as JSON")
                        response_data = response.json()
                        _logger.debug(f"Response data type: {type(response_data)}")
                        
                        # If we got an empty object or list, skip
                        if (isinstance(response_data, dict) and not response_data) or \
                           (isinstance(response_data, list) and not response_data):
                            _logger.warning(f"Empty JSON object/array from {url}")
                            continue
                            
                    except json.JSONDecodeError as je:
                        _logger.error(f"Failed to parse JSON from {url}: {je}")
                        continue
                    
                    # Extract model information from the response
                    model_ids = []
                    
                    # Handle different response formats
                    if isinstance(response_data, dict):
                        _logger.debug("Response is a dictionary")
                        # OpenAI format
                        if "data" in response_data and isinstance(response_data["data"], list):
                            _logger.debug("Found OpenAI format response with 'data' key")
                            for model in response_data["data"]:
                                if isinstance(model, dict) and "id" in model:
                                    model_id = model["id"]
                                    model_name = model.get("name", model_id)
                                    model_ids.append((model_id, model_name))
                        # Another common format
                        elif "models" in response_data and isinstance(response_data["models"], list):
                            _logger.debug("Found response with 'models' key")
                            for model in response_data["models"]:
                                if isinstance(model, dict) and "id" in model:
                                    model_id = model["id"]
                                    model_name = model.get("name", model_id)
                                    model_ids.append((model_id, model_name))
                        else:
                            _logger.debug(f"Dictionary response keys: {list(response_data.keys())}")
                    elif isinstance(response_data, list):
                        _logger.debug("Response is a list")
                        # Simple list format
                        for model in response_data:
                            if isinstance(model, dict) and "id" in model:
                                model_id = model["id"]
                                model_name = model.get("name", model_id)
                                model_ids.append((model_id, model_name))
                    else:
                        _logger.warning(f"Unexpected response data type: {type(response_data)}")
                    
                    if model_ids:
                        _logger.info(f"Found {len(model_ids)} models from endpoint {url}")
                        # Add all found models to our list, avoiding duplicates
                        for model_tuple in model_ids:
                            if model_tuple not in models:
                                models.append(model_tuple)
                        success = True
                        break
                    else:
                        _logger.warning(f"No models found in response from {url}")
                    
                except requests.RequestException as e:
                    _logger.error(f"Request error with endpoint {endpoint}: {e}")
                    continue
                except Exception as e:
                    _logger.error(f"Unexpected error with endpoint {endpoint}: {e}")
                    continue
            
            # If we couldn't find any models from API, we still have our predefined models
            _logger.info(f"Total models found: {len(models)}")
            return models
            
        except Exception as e:
            _logger.error(f"Error in get_available_models: {e}")
            # Return just the default model on any error
            return [(default_model, default_model)]
    
    def chat_completion(self, messages, model=None):
        """
        Send a chat completion request to the OpenWebUI API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model: Model to use (defaults to the configured model)
            
        Returns:
            The response from the OpenWebUI API
        """
        _logger.info("Starting chat_completion request")
        try:
            # For chat completion, we do need a valid API key
            _logger.info("Getting config for chat completion")
            config = self._get_config(raise_if_missing=True)
            
            # Use the provided model or fall back to the configured model
            model = model or config['model']
            _logger.info(f"Using model: {model}")
            
            # Remove trailing slash if present in base_url
            base_url = config['base_url']
            if isinstance(base_url, str) and base_url.endswith('/'):
                base_url = base_url[:-1]
            _logger.info(f"Using base URL: {base_url}")
            
            # Construct the full URL based on the API provider
            if 'openai.com' in base_url:
                # Standard OpenAI API format
                url = f"{base_url}/chat/completions"
            elif 'bemade.org' in base_url:
                # For Bemade's API, try without the v1 path as it's returning 405
                url = f"{base_url}/chat/completions"
            else:
                # Generic format, try standard OpenAI path
                url = f"{base_url}/chat/completions"
                
            _logger.info(f"Full API URL: {url}")
            
            # Set up authentication headers
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            }
            _logger.debug("Authentication headers set up")
            
            # Create the payload
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,  # Add reasonable temperature for more consistent results
                "max_tokens": 4000  # Ensure we get enough tokens for a complete response
            }
            
            _logger.info(f"OpenWebUI API request to: {url}")
            _logger.debug(f"OpenWebUI API payload: {payload}")
            
            try:
                # Make the HTTP request
                _logger.info("Sending POST request to OpenWebUI API")
                response = requests.post(url, headers=headers, json=payload, timeout=60.0)
                _logger.info(f"Response status code: {response.status_code}")
                
                # Log response content for debugging
                _logger.debug(f"Response content (first 500 chars): {response.text[:500]}")
                
                # Raise an exception for any HTTP error
                response.raise_for_status()
                _logger.info("Response status check passed")
                
                # Parse the JSON response
                try:
                    _logger.debug("Parsing response as JSON")
                    response_data = response.json()
                except json.JSONDecodeError as je:
                    _logger.error(f"Failed to parse JSON response: {je}", exc_info=True)
                    _logger.error(f"Response content: {response.text[:500]}")
                    return ""
                
                _logger.debug(f"Response data type: {type(response_data)}")
                if isinstance(response_data, dict):
                    _logger.debug(f"Response keys: {list(response_data.keys())}")
                
                # Extract the content from the response
                if response_data and 'choices' in response_data and response_data['choices']:
                    _logger.info("Successfully extracted content from response")
                    return response_data['choices'][0]['message']['content']
                else:
                    _logger.error(f"Invalid response format from OpenWebUI API: {response_data}")
                    return ""
                    
            except requests.RequestException as re:
                _logger.error(f"Request error calling OpenWebUI API: {re}", exc_info=True)
                raise
            except Exception as e:
                _logger.error(f"Unexpected error in API request: {e}", exc_info=True)
                raise
                    
        except Exception as e:
            _logger.error(f"Error in chat_completion: {e}", exc_info=True)
            raise
