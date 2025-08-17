# Copyright 2025 Bemade
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Bemade Instance Management for Odoo to Odoo Synchronization.

This module extends the base sync instance model with Bemade-specific 
functionality for managing connections to Bemade instances, including support
for OdooRPC and specialized connection handling for Bemade clients.
"""

import logging
import time
import random
import socket
from urllib.parse import urlparse

# Import XML-RPC for standard connections
import xmlrpc.client

# Import OdooRPC conditionally to avoid hard dependency
try:
    import odoorpc
except ImportError:
    odoorpc = None

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# pylint: disable=pointless-string-statement
"""Note sur l'héritage et les champs/méthodes des modèles Odoo

Dans Odoo, l'héritage d'un modèle via `_inherit` permet d'hériter de tous les champs
et méthodes du modèle parent. Cependant, les outils d'analyse statique comme Pylint
et Pyright ne sont pas conscients de ce mécanisme d'héritage et signalent des erreurs
lorsque nous utilisons des attributs définis dans le modèle parent.

Fields hérités du modèle parent 'odoo.sync.instance' (qui ne sont pas redéfinis ici) :
- name: fields.Char        # Nom de l'instance distante
- url: fields.Char         # URL de l'instance distante
- database: fields.Char    # Nom de la base de données distante
- username: fields.Char    # Nom d'utilisateur pour la connexion
- password: fields.Char    # Mot de passe pour la connexion
- connection_type: fields.Selection  # Type de connexion (xmlrpc, jsonrpc)
- connection_timeout: fields.Integer  # Timeout de connexion en secondes
- retry_count: fields.Integer  # Nombre maximal de tentatives de reconnexion
- retry_delay: fields.Integer  # Délai entre les tentatives de reconnexion
- auto_reconnect: fields.Boolean  # Reconnexion automatique
- state: fields.Selection  # État de la connexion
- error_message: fields.Text  # Message d'erreur éventuel
- last_connection: fields.Datetime  # Date et heure de la dernière connexion réussie

Méthodes héritées (ignorées par les linters mais disponibles) :
- test_connection()
- get_connection()
- execute_kw()

Les erreurs lint pour ces attributs et méthodes hérités peuvent être ignorées.
"""

class OdooToBemadeInstance(models.Model):
    """Bemade Remote Odoo instance for synchronization.

    Extends the base sync instance model with Bemade-specific functionality.
    This class adds support for OdooRPC connection type and specialized
    handling for Bemade clients.
    
    Attributes inherited from parent model (odoo.sync.instance):
        name (Char): Name of the remote instance
        url (Char): URL of the remote instance
        database (Char): Database name of the remote instance
        username (Char): Username for authentication
        password (Char): Password for authentication
        connection_type (Selection): Connection type (xmlrpc, jsonrpc)
        connection_timeout (Integer): Timeout in seconds for connection
        retry_count (Integer): Max retries for connection attempts
        retry_delay (Integer): Delay in seconds between retries
        auto_reconnect (Boolean): Whether to reconnect automatically
        state (Selection): Connection state
        error_message (Text): Error message if any
        last_connection (Datetime): Date and time of last successful connection
        
    Note to static analyzers:
        The fields and methods mentioned above are inherited from the parent model 
        and are available at runtime through Odoo's inheritance mechanism.
        Lint errors for these attributes can safely be ignored.
    """
    # Fields inherited from parent class - for linters only
    # pyright: ignore[reportAttributeAccessIssue]
    name: str
    url: str
    database: str
    username: str
    password: str
    connection_type: fields.Selection
    connection_timeout: int
    retry_count: int
    retry_delay: int
    auto_reconnect: bool
    state: fields.Selection
    error_message: str
    last_connection: fields.Datetime

    _name = 'odoo.to.bemade.instance'
    _description = 'Bemade Remote Odoo Instance'
    _inherit = 'odoo.sync.instance'

    # Champs spécifiques à Bemade
    # Note: Legacy API key functionality has been removed
    # Use the built-in api_key field from parent model instead
    
    # Override connection_type to add OdooRPC option
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
    
    model_ids = fields.One2many(
        'odoo.to.bemade.sync.model', 
        'bemade_instance_id',
        string='Modèles synchronisés',
        help='Modèles configurés pour la synchronisation avec cette instance',
    )
    
    log_ids = fields.One2many(
        'odoo.to.bemade.sync.log',
        'bemade_instance_id',
        string='Synchronization Logs',
    )
    
    connection_timeout = fields.Integer(
        string='Connection Timeout',
        default=60,
        help='Timeout in seconds for the connection',
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=3,
        help='Number of times to retry failed connections',
    )
    
    retry_delay = fields.Integer(
        string='Retry Delay',
        default=5,
        help='Delay between retries in seconds',
    )
    
    auto_reconnect = fields.Boolean(
        string='Auto Reconnect',
        default=True,
        help='Automatically reconnect if connection is lost',
    )
    
    # Remarque: model_ids et log_ids sont déjà définis ci-dessus, pas besoin de duplication
    
    # NOTE: The custom onchange method was removed as it had an incorrect signature
    # and was causing TypeError when creating new instances

    @api.onchange('url')
    def _onchange_url(self):
        """Reset state when URL changes.
        
        Extends the parent method to add Bemade-specific behavior if needed.
        
        Note: Although linters may report url, state, and error_message as unknown attributes,
        they are inherited from the parent model and are available at runtime.
        """
        # pylint: disable=attribute-defined-outside-init
        # Fields inherited from parent model: url, state, error_message
        if self.url != self._origin.url:
            self.write({'state': 'draft', 'error_message': False})

    def test_connection(self):
        """Test the connection to the remote Odoo instance.
        
        If the connection type is 'odoorpc', use the specialized method,
        otherwise fall back to the parent implementation.
        
        Note: connection_type is inherited from the parent model, but linters won't detect this.
        """
        self.ensure_one()
        
        # Field inherited from parent model: connection_type
        # pylint: disable=no-member
        if self.connection_type == 'odoorpc':
            return self._test_odoorpc_connection()
            
        # Call the parent method - linters might not recognize this as valid
        # pylint: disable=no-member
        result = super(OdooToBemadeInstance, self).test_connection()
        
        # Create a log entry with the result
        if result:
            self.env['odoo.to.bemade.sync.log'].log(
                operation='test_connection',
                model='odoo.to.bemade.instance',
                record_id=self.id,
                result='success',
                details=f"Successfully connected to {self.name} using {self.connection_type}",
                instance_id=self.id
                # queue_id will be automatically created by the log method
            )
        else:
            self.env['odoo.to.bemade.sync.log'].log(
                operation='test_connection',
                model='odoo.to.bemade.instance',
                record_id=self.id,
                result='error',
                details=f"Connection test failed: {self.error_message}",
                instance_id=self.id
                # queue_id will be automatically created by the log method
            )
        
        return result

    def _test_xmlrpc_connection(self):
        """Override parent's XML-RPC connection test to support API key authentication."""
        self.ensure_one()
        try:
            # Validate URL format
            if not self.url:
                raise UserError("L'URL est requise pour tester la connexion")
                
            # Parse URL to extract connection details
            parsed_url = urlparse(self.url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise UserError("Format d'URL invalide. Exemple valide: https://exemple.odoo.com")
            
            # Get API token for authentication (Odoo 18+ expects dict with scope/key during authenticate)
            api_token = self._decrypt_sensitive_data() or self.api_key
            
            # Timeout-aware XML-RPC transport
            class TimeoutTransport(xmlrpc.client.Transport):
                def __init__(self, timeout=None, use_datetime=False):
                    super().__init__(use_datetime=use_datetime)
                    self.timeout = timeout
                def make_connection(self, host):
                    conn = super().make_connection(host)
                    try:
                        conn.timeout = self.timeout
                    except Exception:
                        pass
                    return conn

            transport = TimeoutTransport(timeout=self.connection_timeout or 30)
            common = xmlrpc.client.ServerProxy(
                f'{self.url}/xmlrpc/2/common', transport=transport, allow_none=True
            )
            uid = common.authenticate(
                self.database, self.username, {'scope': 'rpc', 'key': api_token}, {}
            )
            
            if uid:
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
                return True
            else:
                raise UserError('Échec d\'authentification')
                
        except UserError as e:
            # Pass through our UserError without modification
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            _logger.error("Erreur d'authentification XML-RPC: %s", str(e))
            return False
            
        except (ConnectionError, TimeoutError, xmlrpc.client.Fault, xmlrpc.client.ProtocolError) as e:
            # Catch specific exceptions that can be raised during XML-RPC connection
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            _logger.error("Erreur de connexion XML-RPC: %s", str(e))
            return False
            
        except Exception as e:  # pylint: disable=broad-except
            # Fall back for any unexpected exceptions
            self.write({
                'state': 'error',
                'error_message': f"Erreur inattendue: {str(e)}"
            })
            _logger.error("Erreur inattendue XML-RPC: %s", str(e))
            return False

    def _get_xmlrpc_connection(self):
        """Override parent's XML-RPC connection method to support API key authentication."""
        # Get API token for authentication
        api_token = self._decrypt_sensitive_data() or self.api_key

        # Timeout-aware transport
        class TimeoutTransport(xmlrpc.client.Transport):
            def __init__(self, timeout=None, use_datetime=False):
                super().__init__(use_datetime=use_datetime)
                self.timeout = timeout
            def make_connection(self, host):
                conn = super().make_connection(host)
                try:
                    conn.timeout = self.timeout
                except Exception:
                    pass
                return conn

        transport = TimeoutTransport(timeout=self.connection_timeout or 30)
        common = xmlrpc.client.ServerProxy(
            f'{self.url}/xmlrpc/2/common', transport=transport, allow_none=True
        )
        uid = common.authenticate(
            self.database, self.username, {'scope': 'rpc', 'key': api_token}, {}
        )
        models = xmlrpc.client.ServerProxy(
            f'{self.url}/xmlrpc/2/object', transport=transport, allow_none=True
        )
        return models, uid

    def _test_odoorpc_connection(self):
        """Test connection using OdooRPC library.
        
        This method is specific to the Bemade implementation and handles
        the OdooRPC connection type that's not in the parent model.
        """
        # Set the state to indicate testing is in progress
        self.write({'state': 'testing'})
        
        try:
            # Check if OdooRPC library is installed
            try:
                import odoorpc
            except ImportError as exc:
                raise ImportError(
                    "La bibliothèque OdooRPC n'est pas installée. "
                    "Installez-la avec 'pip install odoorpc'"
                ) from exc
            
            # Parse URL to extract connection details (ensure scheme present)
            raw_url = (self.url or '').strip()
            parsed_url = urlparse(raw_url)
            if not parsed_url.scheme:
                raw_url = f'https://{raw_url}'
                parsed_url = urlparse(raw_url)
            protocol = 'jsonrpc+ssl' if parsed_url.scheme == 'https' else 'jsonrpc'
            host = parsed_url.hostname
            if not host:
                raise UserError("URL invalide: hôte introuvable. Incluez le schéma (https://) et le domaine.")
            
            # Determine port using parsed value or defaults
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)

            # Preflight TCP connectivity to avoid hangs (DNS/TLS/connect)
            _logger.info(
                "[Bemade Sync][OdooRPC] Preflight TCP connect to %s:%s (timeout=%ss)",
                host, port, self.connection_timeout or 30,
            )
            try:
                start = time.time()
                with socket.create_connection((host, port), timeout=self.connection_timeout or 30):
                    pass
                _logger.info(
                    "[Bemade Sync][OdooRPC] Preflight OK in %.3fs",
                    time.time() - start,
                )
            except Exception as e:
                raise UserError(f"Impossible de joindre {host}:{port} - {e}") from e

            # Attempt connection with OdooRPC
            odoo = odoorpc.ODOO(
                host,
                protocol=protocol,
                port=port
            )
            # Configure library timeout to prevent hanging connections
            if hasattr(odoo, 'config'):
                odoo.config['timeout'] = self.connection_timeout or 30
            _logger.info(
                "[Bemade Sync][OdooRPC] Connecting to %s:%s protocol=%s timeout=%ss",
                host, port, protocol, self.connection_timeout or 30,
            )
            
            # Try to login with credentials
            api_key = self._decrypt_sensitive_data() or self.api_key
            prev_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self.connection_timeout or 30)
            try:
                _logger.info(
                    "[Bemade Sync][OdooRPC] Logging in db=%s user=%s",
                    self.database, self.username,
                )
                odoo.login(self.database, self.username, api_key)
            finally:
                try:
                    socket.setdefaulttimeout(prev_timeout)
                except Exception:
                    pass
            
            # If successful, update record state
            if odoo.env:
                self.write({
                    'state': 'connected',
                    'last_connection': fields.Datetime.now(),
                    'error_message': False
                })
                # Success is logged in the main test_connection method
                # No need to log here to avoid duplicate entries
                return True
            else:
                # This should rarely happen as login usually raises an exception
                raise UserError('Échec d\'authentification')
                
        except UserError as e:
            # Pass through our UserError without modification
            error_msg = str(e)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            # Error is logged in the main test_connection method
            # No need to log here to avoid duplicate entries
            _logger.error("Erreur d'authentification OdooRPC: %s", error_msg)
            return False
            
        except (ConnectionError, TimeoutError, socket.timeout, ValueError, TypeError) as e:
            # Catch specific exceptions that can be raised during connection
            error_msg = str(e)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            # Error is logged in the main test_connection method
            # No need to log here to avoid duplicate entries
            _logger.error("Erreur de connexion OdooRPC: %s", error_msg)
            return False
        except Exception as e:  # pylint: disable=broad-except
            # Fall back for any unexpected exceptions
            error_msg = str(e)
            self.write({
                'state': 'error',
                'error_message': f"Erreur inattendue: {error_msg}"
            })
            # Create error log entry
            self.env['odoo.to.bemade.sync.log'].log(
                operation='test_odoorpc_connection',
                model='odoo.to.bemade.instance',
                record_id=self.id,
                result='error',
                details=f"Unexpected error: {error_msg}",
                instance_id=self.id
                # queue_id will be automatically created by the log method
            )
            _logger.error("Erreur inattendue OdooRPC: %s", error_msg)
            return False

    def get_connection(self):
        """Return an active connection to the remote instance.
        
        This method extends the parent implementation to handle the
        OdooRPC connection type in addition to the parent's connection types.
        """
        self.ensure_one()
        
        # Ensure we have an active connection
        if self.state != 'connected':
            self.test_connection()
            if self.state != 'connected':
                # Use UserError for better user experience
                raise UserError(f'Impossible de se connecter à {self.name}: {self.error_message}')
        
        # Handle OdooRPC connection type
        if self.connection_type == 'odoorpc':
            return self._get_odoorpc_connection()
            
        # Use parent implementation for other connection types
        return super(OdooToBemadeInstance, self).get_connection()

    def _get_odoorpc_connection(self):
        """Get a connection to the remote Odoo instance using OdooRPC.
        
        Returns a connection object that can be used to interact with the remote instance.
        
        Returns:
            OdooRPCWrapper: A wrapped OdooRPC connection object that provides compatible interface
            
        Raises:
            ImportError: When OdooRPC library is not installed
            UserError: When connection fails due to authentication issues
            Exception: For other connection failures
        """
        try:
            # Check if OdooRPC library is installed
            try:
                import odoorpc
            except ImportError as exc:
                raise ImportError(
                    "La bibliothèque OdooRPC n'est pas installée. "
                    "Installez-la avec 'pip install odoorpc'"
                ) from exc
                
            # Parse URL to extract connection details (ensure scheme present)
            raw_url = (self.url or '').strip()
            parsed_url = urlparse(raw_url)
            if not parsed_url.scheme:
                raw_url = f'https://{raw_url}'
                parsed_url = urlparse(raw_url)
            is_https = parsed_url.scheme == 'https'
            protocol = 'jsonrpc+ssl' if is_https else 'jsonrpc'
            host = parsed_url.hostname
            if not host:
                raise UserError("URL invalide: hôte introuvable. Incluez le schéma (https://) et le domaine.")
            port = parsed_url.port or (443 if is_https else 80)

            # Preflight TCP connectivity to avoid hangs (DNS/TLS/connect)
            _logger.info(
                "[Bemade Sync][OdooRPC] get_connection preflight TCP to %s:%s (timeout=%ss)",
                host, port, self.connection_timeout or 30,
            )
            try:
                with socket.create_connection((host, port), timeout=self.connection_timeout or 30):
                    pass
            except Exception as e:
                raise UserError(f"Impossible de joindre {host}:{port} - {e}") from e
            
            # Create OdooRPC connection
            odoo = odoorpc.ODOO(
                host,
                protocol=protocol,
                port=port
            )
            # Set timeout via attribute if available
            if hasattr(odoo, 'config'):
                odoo.config['timeout'] = self.connection_timeout or 30
            _logger.info(
                "[Bemade Sync][OdooRPC] get_connection -> %s:%s protocol=%s timeout=%ss",
                host, port, protocol, self.connection_timeout or 30,
            )
            
            # Login with API token credentials
            api_token = self._decrypt_sensitive_data() or self.api_key
            odoo.login(self.database, self.username, api_token)
            
            # Create a wrapper class to make OdooRPC interface compatible with xmlrpc/jsonrpc
            class OdooRPCWrapper:
                """Wrapper class to provide a compatible interface with XML-RPC."""
                def __init__(self, odoo_instance):
                    self.odoo = odoo_instance
                    
                def execute_kw(self, db, uid, password, model, method, args, kwargs=None):
                    """Mimics XML-RPC's execute_kw but uses OdooRPC internally.
                    
                    Args:
                        db: Database name (unused for OdooRPC, required for compatibility)
                        uid: User ID (unused for OdooRPC, required for compatibility)
                        password: Password (unused for OdooRPC, required for compatibility)
                        model: Model name to call
                        method: Method name to call on the model
                        args: Positional arguments for the method
                        kwargs: Keyword arguments for the method
                    
                    Returns:
                        Result of the method call
                        
                    Raises:
                        Exception: When the method call fails
                    """
                    # These parameters are required for compatibility but not used
                    # with OdooRPC since we're already logged in
                    # pylint: disable=unused-argument
                    
                    # Handle args and kwargs correctly
                    args = args or []
                    kwargs = kwargs or {}

                    try:
                        # OdooRPC has a different API for standard vs custom methods
                        if model in self.odoo.env and hasattr(self.odoo.env[model], method):
                            # Use the standard API for methods like 'search', 'read', etc.
                            model_obj = self.odoo.env[model]
                            method_obj = getattr(model_obj, method)
                            return method_obj(*args, **kwargs)
                        else:
                            # Use execute for custom methods
                            return self.odoo.execute(model, method, *args, **kwargs)
                    except Exception as e:
                        _logger.error(
                            "Erreur lors de l'exécution de %s.%s via OdooRPC: %s", 
                            model, method, str(e)
                        )
                        raise
                # pylint: enable=unused-argument
            
            # Update connection state on success
            self.write({
                'state': 'connected',
                'last_connection': fields.Datetime.now(),
                'error_message': False
            })
            
            # Return wrapper and uid, similar to how XML-RPC connections work
            wrapper = OdooRPCWrapper(odoo)
            return wrapper, odoo.env.uid
            
        except (ConnectionError, TimeoutError) as e:
            # Specific error handling for connection and timeout issues
            error_msg = f"Délai d'attente dépassé lors de la connexion à {self.name}: {e}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            _logger.error("Erreur de connexion/timeout dans _get_odoorpc_connection: %s", str(e))
            raise UserError(error_msg) from e
        except (ValueError, TypeError) as e:
            # Handle value or type errors
            error_msg = f"Paramètres invalides pour la connexion à {self.name}: {e}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            _logger.error("Erreur de paramètres dans _get_odoorpc_connection: %s", str(e))
            raise UserError(error_msg) from e
        except Exception as e:  # pylint: disable=broad-except
            # Fall back for any unexpected exceptions
            error_msg = f"Échec lors de la connexion à {self.name}: {e}"
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            _logger.error("Erreur inattendue dans _get_odoorpc_connection: %s", str(e))
            raise UserError(error_msg) from e
            
    def execute_kw(self, model, method, args=None, kwargs=None):
        """Execute a method on the remote model using the appropriate connection type.
        
        This method provides a unified interface for executing methods on remote models,
        abstracting away the differences between XML-RPC and OdooRPC.
        
        Args:
            model (str): Name of the model on the remote instance
            method (str): Name of the method to execute
            args (list, optional): Positional arguments to pass to the method
            kwargs (dict, optional): Keyword arguments to pass to the method
            
        Returns:
            object: Result of the method execution
            
        Raises:
            UserError: When connection is not established or fails
            ValidationError: When method execution fails on the remote instance
        """
        self.ensure_one()
        args = args or []
        kwargs = kwargs or {}
        
        # Ensure we have a connection
        if self.state != 'connected':
            _logger.debug("Connection to %s not established. Attempting to connect.", self.name)
            self.test_connection()
            if self.state != 'connected':
                raise UserError(f"Cannot execute method on {self.name}: {self.error_message}")
        
        try:
            # Get connection based on connection type
            connection = self.get_connection()
            
            # For OdooRPC connection, use the wrapper's execute_kw method
            if self.connection_type == 'odoorpc':
                _logger.debug("Executing %s.%s via OdooRPC on %s", model, method, self.name)
                # OdooRPC wrapper returns a tuple (wrapper, uid)
                wrapper, uid = connection
                # Use the wrapper's execute_kw method
                return wrapper.execute_kw(
                    self.database, uid, self.password, 
                    model, method, args, kwargs
                )
            else:
                # For XML-RPC, delegate to parent implementation
                _logger.debug("Executing %s.%s via standard RPC on %s", model, method, self.name)
                # XML-RPC connection returns a tuple (models, uid)
                models, uid = connection
                api_token = self._decrypt_sensitive_data() or self.api_key
                # Execute the method directly on the model with API token
                return models.execute_kw(
                    self.database, uid, api_token,
                    model, method, args, kwargs
                )
                
        except Exception as e:
            error_msg = f"Error executing {model}.{method} on {self.name}: {str(e)}"
            _logger.error(error_msg)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            raise ValidationError(error_msg) from e
