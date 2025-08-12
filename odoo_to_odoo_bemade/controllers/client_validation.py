# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Client Validation Controller.

This controller handles XML-RPC requests from client instances for
validating API tokens and establishing connections.
"""

import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class ClientValidationController(http.Controller):
    """Controller for handling client validation requests."""
    
    def _validate_client(self, client_key):
        """Validate a client connection using the client key.
        
        Args:
            client_key (str): The client key to validate
            
        Returns:
            bool: True if the client is valid, False otherwise
        """
        # Find the project with this client key
        project = request.env['project.project'].sudo().search([
            ('client_key', '=', client_key)
        ], limit=1)
        
        if not project:
            _logger.warning(f"Client validation failed: No project found with client key {client_key}")
            return False
            
        if not project.is_client_project:
            _logger.warning(f"Client validation failed: Project {project.id} is not marked as client project")
            return False
            
        # Create or update the client instance
        instance_vals = {
            'name': f"Client {client_key}",
            'url': request.httprequest.remote_addr,
            'connection_type': 'xmlrpc',
        }
        
        if project.client_instance_id:
            project.client_instance_id.sudo().write(instance_vals)
        else:
            instance = request.env['odoo.to.bemade.instance'].sudo().create(instance_vals)
            project.sudo().write({'client_instance_id': instance.id})
            
        _logger.info(f"Client validation successful for project {project.id}")
        return True
    
    def _authenticate_client(self, client_key, api_token):
        """Authenticate a client using client key and API token.
        
        Args:
            client_key (str): The client key
            api_token (str): The API token
            
        Returns:
            dict: Authentication result with company info and models
        """
        # Find the project with this client key
        project = request.env['project.project'].sudo().search([
            ('client_key', '=', client_key),
            ('client_api_token', '=', api_token)
        ], limit=1)
        
        if not project:
            _logger.warning(f"Client authentication failed: Invalid credentials for client key {client_key}")
            return {
                'success': False,
                'error': 'Invalid client key or API token'
            }
            
        if not project.is_client_project:
            _logger.warning(f"Client authentication failed: Project {project.id} is not marked as client project")
            return {
                'success': False,
                'error': 'Project is not configured as client project'
            }
            
        # Get company information
        company = request.env.user.company_id
        
        # Get available sync models for this project
        models = []
        for model in project.sync_model_ids:
            models.append({
                'model': model.model_id.model,
                'target_model': model.target_model,
                'field_mapping': model.field_mapping,
                'domain': model.sync_domain,
            })
            
        result = {
            'success': True,
            'company_name': company.name,
            'models': models
        }
        
        _logger.info(f"Client authentication successful for project {project.id}")
        return result
        try:
            # Find the project with the matching API token
            project = request.env['project.project'].sudo().search([
                ('client_api_token', '=', api_key),
                ('is_client_project', '=', True)
            ], limit=1)
            
            if not project:
                return {
                    'success': False,
                    'message': 'Clé API invalide'
                }
            
            
            return {
                'success': True,
                'company_name': project.company_id.name if project.company_id else project.name,
                'models': model_data
            }
            
        except Exception as e:
            _logger.error("Erreur de validation client: %s", str(e))
            return {
                'success': False,
                'message': 'Erreur de validation'
            }
    
    def _authenticate_client(self, client_key, api_key, instance_id):
        """Authenticate client and return user ID.
        
        Args:
            client_key (str): The client key provided by the user
            api_key (str): The API key provided by the user
            instance_id (str): The unique instance ID of the client
            
        Returns:
            int or False: User ID if authentication successful, False otherwise
        """
        try:
            # Find the project with the matching API token
            project = request.env['project.project'].sudo().search([
                ('client_api_token', '=', api_key),
                ('is_client_project', '=', True)
            ], limit=1)
            
            if not project:
                return False
            
            # Check if the client key matches
            # For now, we'll use the project ID as the client key
            if str(project.id) != client_key:
                return False
            
            # Return a valid user ID for synchronization
            # In a real implementation, this would be a specific sync user
            return request.env.ref('base.user_admin').id
            
        except Exception as e:
            _logger.error("Erreur d'authentification client: %s", str(e))
            return False
