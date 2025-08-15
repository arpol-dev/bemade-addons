# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Remote Odoo Instance Management.

This module handles the configuration and connection management for remote
Odoo instances. It provides functionality to store connection credentials,
test connections, and maintain the connection state with remote instances.
"""

import logging
import xmlrpc.client
import time
import random
import json
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlparse

# Import XML-RPC for standard connections
# xmlrpc.client already imported above

# Import OdooRPC conditionally to avoid hard dependency
try:
    import odoorpc
except ImportError:
    odoorpc = None

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..utils.encryption import encrypt_value, decrypt_value

_logger = logging.getLogger(__name__)

class OdooSyncInstance(models.Model):
    """Remote Odoo instance for synchronization.

    This model stores connection information and credentials for remote Odoo instances
    that will be synchronized with the current instance.
    """

    _name = 'odoo.sync.instance'
    _description = 'Remote Odoo Instance'
    
    # Type hints for static analysis tools
    name: fields.Char
    url: fields.Char
    database: fields.Char
    username: fields.Char
    api_key: fields.Char
    encrypted_api_key: fields.Char
    connection_type: fields.Selection
    state: fields.Selection
    last_connection: fields.Datetime
    error_message: fields.Text

    name = fields.Char(
        string='Name', 
        required=True,
        help='Name to identify this remote instance',
    )

    url = fields.Char(
        string='URL', 
        required=True,
        help='Base URL of the remote Odoo instance',
    )

    database = fields.Char(
        string='Database', 
        required=True,
        help='Database name on the remote instance',
    )
    
    username = fields.Char(
        string='Technical User', 
        required=True,
        help='Username of the technical user for synchronization',
    )
    
    # API Key for Odoo's native token authentication
    api_key = fields.Char(
        string='API Token',
        required=True,
        copy=False,
        help='API token for Odoo\'s native authentication system',
    )
    
    # Encrypted storage for API key
    encrypted_api_key = fields.Char(
        string='Encrypted API Token',
        copy=False,
        help='Encrypted API token for secure storage',
    )
    
    connection_type = fields.Selection(
        selection=[
            ('xmlrpc', 'XML-RPC'),
            ('jsonrpc', 'JSON-RPC'),
            ('odoorpc', 'OdooRPC')
        ],
        string='Connection Type',
        default='xmlrpc',
        required=True,
        help='Protocol to use for connection to the remote instance',
    )
    
    connection_timeout = fields.Integer(
        string='Connection Timeout',
        default=30,
        help='Timeout in seconds for connection to the remote instance',
    )
    
    retry_count = fields.Integer(
        string='Max Retries',
        default=3,
        help='Maximum number of connection retry attempts',
    )
    
    conflict_resolution_strategy = fields.Selection([
        ('manual', 'Manual Resolution'),
        ('timestamp', 'Newest Wins'),
        ('source_priority', 'Source Instance Wins'),
        ('destination_priority', 'Destination Instance Wins')
    ], string='Conflict Resolution Strategy', default='manual',
       help='Strategy for resolving synchronization conflicts with this instance')
    
    retry_delay = fields.Integer(
        string='Retry Delay',
        default=5,
        help='Delay in seconds between retry attempts',
    )
    
    auto_reconnect = fields.Boolean(
        string='Auto Reconnect',
        default=True,
        help='Automatically attempt to reconnect when connection is lost',
    )

    active = fields.Boolean(
        string='Active', 
        default=True,
        help='Whether this instance is active for synchronization',
    )
    
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('testing', 'Testing Connection'),
            ('connected', 'Connected'),
            ('error', 'Error')
        ], 
        default='draft', 
        string='State',
        help='Current state of the connection',
    )

    last_connection = fields.Datetime(
        string='Last Connection',
        help='Timestamp of the last successful connection',
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Details of the last error that occurred',
    )

    @api.onchange('url')
    def _onchange_url(self):
        """Reset state when URL changes."""
        self.state = 'draft'
        
    def test_connection(self):
        """Test the connection to the remote Odoo instance.
        
        This method attempts to authenticate with the remote instance
        and updates the connection state accordingly.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        self.ensure_one()
        
        if self.connection_type == 'xmlrpc':
            return self._test_xmlrpc_connection()
        elif self.connection_type == 'jsonrpc':
            return self._test_jsonrpc_connection()
        elif self.connection_type == 'odoorpc':
            return self._test_odoorpc_connection()
        else:
            raise UserError(f"Type de connexion non supporté: {self.connection_type}")
    
    def _encrypt_sensitive_data(self):
        """Encrypt API token for secure storage."""
        for record in self:
            # Only encrypt API key (no password handling)
            if record.api_key and not record.encrypted_api_key:
                record.encrypted_api_key = encrypt_value(record.env, record.api_key)
                # Don't clear API key field - keep it for display/editing

    def _decrypt_sensitive_data(self):
        """Decrypt API token for authentication."""
        self.ensure_one()
        # Only use API token for authentication (no password fallback)
        if self.encrypted_api_key:
            return decrypt_value(self.env, self.encrypted_api_key)
        return self.api_key
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to encrypt sensitive data."""
        records = super().create(vals_list)
        records._encrypt_sensitive_data()
        return records
    
    def write(self, vals):
        """Override write to encrypt sensitive data."""
        result = super().write(vals)
        self._encrypt_sensitive_data()
        return result
    
    def _test_xmlrpc_connection(self):
        """Test XML-RPC connection to the remote instance using official Odoo API key format."""
        self.ensure_one()
        self.write({'state': 'testing'})
        
        try:
            # Validate URL
            if not self.url:
                raise UserError("URL is required")
            
            # Parse URL
            url = self.url.strip()
            parsed_url = urlparse(url)
            
            # Ensure proper scheme
            if not parsed_url.scheme:
                url = f"http://{url}"
                parsed_url = urlparse(url)
            
            scheme = parsed_url.scheme
            netloc = parsed_url.netloc
            
            if not netloc:
                raise UserError(f"Invalid URL format: {url}")
            
            # Get API key
            api_token = self._decrypt_sensitive_data() or self.api_key
            if not api_token:
                raise UserError("No API key found")
            
            # Create XML-RPC client
            xmlrpc_url = f"{scheme}://{netloc}/xmlrpc/2/common"
            _logger.info("[SYNC DEBUG] Attempting XML-RPC connection to: %s", xmlrpc_url)
            
            common = xmlrpc.client.ServerProxy(xmlrpc_url)
            
            # For XML-RPC, use raw API key string (not dict format)
            # This provides compatibility with older Odoo versions
            uid = common.authenticate(self.database, self.username, api_token, {})
            if uid:
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
                return True
            else:
                error_msg = "Authentication failed - invalid credentials"
                _logger.error("[SYNC DEBUG] %s", error_msg)
                self.write({
                    'state': 'error',
                    'error_message': error_msg
                })
                raise UserError(error_msg)
                
        except UserError:
            # Re-raise UserError as it already has appropriate message
            raise
        except Exception as e:
            # Handle connection errors and other exceptions
            error_msg = f"XML-RPC connection test failed: {str(e)}"
            _logger.error("[SYNC DEBUG] %s", error_msg)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            raise UserError(error_msg)

    def get_connection(self):
        """Return an active connection to the remote instance.
        
        Returns:
            tuple: (models_proxy, user_id) for XML-RPC connection
        
        Raises:
            UserError: If connection fails
        """
        self.ensure_one()
        
        # Ensure we have an active connection
        if self.state != 'connected':
            self.test_connection()
            if self.state != 'connected':
                # Use UserError for better user experience
                raise UserError(f'Impossible de se connecter à {self.name}: {self.error_message}')
        
        # Return appropriate connection based on connection type
        if self.connection_type == 'xmlrpc':
            return self._get_xmlrpc_connection()
        elif self.connection_type == 'jsonrpc':
            return self._get_jsonrpc_connection()
        elif self.connection_type == 'odoorpc':
            return self._get_odoorpc_connection()
        else:
            raise UserError(f"Type de connexion non supporté: {self.connection_type}")
    
    def _get_xmlrpc_connection(self):
        """Get XML-RPC connection to the remote instance using API key string."""
        # Get API key for authentication
        api_token = self._decrypt_sensitive_data()
        
        # For XML-RPC, use raw API key string (not dict format)
        common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        uid = common.authenticate(self.database, self.username, api_token, {})
        models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
        
        return models, uid
        
    def execute_kw(self, model, method, args=None, kwargs=None):
        """Execute a method on the remote Odoo instance using API key string.
        
        This method provides a unified interface for executing methods on remote models
        regardless of the connection type.
        
        Args:
            model (str): The model name
            method (str): The method to call
            args (list, optional): Positional arguments
            kwargs (dict, optional): Keyword arguments
            
        Returns:
            The result of the method call
            
        Raises:
            UserError: If execution fails
        """
        self.ensure_one()
        
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
            
        try:
            models, uid = self.get_connection()
            # Get API key for authentication
            api_token = self._decrypt_sensitive_data()
            
            # Use raw API key string for all protocols
            result = models.execute_kw(
                self.database, uid, api_token,
                model, method, args, kwargs
            )
            return result
            
        except UserError:
            # Re-raise UserError as it already has appropriate message
            raise
            
        except Exception as e:
            error_msg = f"OdooRPC connection failed: {str(e)}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            raise UserError(error_msg)

    def _get_jsonrpc_connection(self):
        """Get JSON-RPC connection to the remote instance using API token authentication."""
        try:
            # Get decrypted credentials (API token)
            api_token = self._decrypt_sensitive_data()
            
            # Build JSON-RPC endpoint URL
            jsonrpc_url = f'{self.url}/jsonrpc'
            
            # Create JSON-RPC client
            class JsonRpcClient:
                def __init__(self, url, database, username, api_token):
                    self.url = url
                    self.database = database
                    self.username = username
                    self.api_token = api_token
                    self.uid = None
                    
                def authenticate(self):
                    """Authenticate using official Odoo API key format."""
                    auth_data = {
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "service": "common",
                            "method": "authenticate",
                            "args": [
                                self.database,
                                self.username,
                                {'scope': 'rpc', 'key': self.api_token},
                                {}
                            ]
                        },
                        "id": random.randint(1, 1000000)
                    }
                    
                    response = self._send_request(self.url, auth_data)
                    if response.get('result'):
                        self.uid = response['result']
                        return self.uid
                    else:
                        error = response.get('error', {})
                        raise UserError(f"Authentication failed: {error.get('message', 'Unknown error')}")
                
                def execute_kw(self, model, method, args=None, kwargs=None):
                    """Execute a method on the remote model."""
                    if args is None:
                        args = []
                    if kwargs is None:
                        kwargs = {}
                    
                    data = {
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "service": "object",
                            "method": "execute_kw",
                            "args": [self.database, self.uid, self.api_token, model, method, args, kwargs]
                        },
                        "id": random.randint(1, 1000000)
                    }
                    
                    response = self._send_request(self.url, data)
                    if response.get('error'):
                        error = response.get('error', {})
                        raise UserError(f"Remote method call failed: {error.get('message', 'Unknown error')}")
                    return response.get('result')
                
                def _send_request(self, url, data):
                    """Send JSON-RPC request."""
                    try:
                        headers = {
                            'Content-Type': 'application/json',
                            'User-Agent': 'Odoo-Sync/1.0'
                        }
                        
                        request = urllib.request.Request(
                            url,
                            data=json.dumps(data).encode('utf-8'),
                            headers=headers,
                            method='POST'
                        )
                        
                        with urllib.request.urlopen(request, timeout=30) as response:
                            response_data = response.read().decode('utf-8')
                            return json.loads(response_data)
                            
                    except urllib.error.HTTPError as e:
                        error_content = e.read().decode('utf-8')
                        try:
                            error_data = json.loads(error_content)
                            raise UserError(f"HTTP Error {e.code}: {error_data.get('error', {}).get('message', str(e))}")
                        except:
                            raise UserError(f"HTTP Error {e.code}: {str(e)}")
                    except urllib.error.URLError as e:
                        raise UserError(f"Connection Error: {str(e)}")
                    except Exception as e:
                        raise UserError(f"Request Error: {str(e)}")
            
            client = JsonRpcClient(jsonrpc_url, self.database, self.username, api_token)
            client.authenticate()
            return client
            
        except Exception as e:
            error_msg = f"Connection Error: {str(e)}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            return False

    def _test_jsonrpc_connection(self):
        """Test JSON-RPC connection to the remote instance using API key string."""
        self.ensure_one()
        self.write({'state': 'testing'})
        
        try:
            if not self.url:
                raise UserError("URL is required")
            
            # Get API key for authentication
            api_token = self._decrypt_sensitive_data()
            if not api_token:
                raise UserError("No API key found")
            
            # Parse and validate URL
            url = self.url.strip()
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                url = f"http://{url}"
                parsed_url = urlparse(url)
            
            scheme = parsed_url.scheme
            netloc = parsed_url.netloc
            if not netloc:
                raise UserError(f"Invalid URL format: {url}")
            
            # Build JSON-RPC endpoint URL
            jsonrpc_url = f"{scheme}://{netloc}/jsonrpc"
            
            # Prepare authentication request
            data = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "service": "common",
                    "method": "authenticate",
                    "args": [self.database, self.username, api_token, {}]
                },
                "id": 1
            }
            
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(jsonrpc_url, data=json.dumps(data).encode('utf-8'), headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))
            
            if 'result' in response_data and response_data['result']:
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
                return True
            else:
                raise UserError("JSON-RPC authentication failed")
                
        except Exception as e:
            error_msg = str(e)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            raise UserError(error_msg)

    def _test_odoorpc_connection(self):
        """Get OdooRPC connection to the remote instance using API token authentication."""
        if odoorpc is None:
            raise UserError("La bibliothèque OdooRPC n'est pas installée. Installez-la avec: pip install odoorpc")
        
        try:
            password = self._decrypt_sensitive_data()
            
            # Parse URL to extract host, port, and protocol
            parsed_url = urlparse(self.url)
            protocol = 'jsonrpc+ssl' if parsed_url.scheme == 'https' else 'jsonrpc'
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            host = parsed_url.hostname
            
            # Create OdooRPC connection
            odoo = odoorpc.ODOO(host, port=port, protocol=protocol)
            
            # Authenticate using API token
            # Always use API token authentication in Odoo 17-18
            odoo.login(self.database, self.username, password)
            
            return odoo
            
        except Exception as e:
            raise UserError(f"Erreur de connexion OdooRPC: {str(e)}")
