import os
import logging
import socket
from . import models
from . import controllers
from . import wizards

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """Post-install hook to set up Bemade-specific configuration."""
    # Set default configuration parameters for Bemade instances
    ICP = env['ir.config_parameter']
    
    # Ensure the parameters exist with default values
    defaults = {
        'bemade.sync.default_url': 'https://odoo.bemade.org',
        'bemade.sync.default_database': 'bemade',
        'bemade.sync.default_username': 'sync_user',
        'bemade.sync.default_connection_type': 'odoorpc',
        'bemade.sync.default_timeout': '30',
        'bemade.sync.default_retry_count': '3',
        'bemade.sync.default_retry_delay': '5',
    }
    
    for key, value in defaults.items():
        if not ICP.get_param(key):
            ICP.set_param(key, value)

    # Optionally inject API key and other overrides from environment variables (never hardcode secrets)
    # Accepted env vars: BEMADE_SYNC_DEFAULT_URL, _DATABASE, _USERNAME, _API_KEY, _CONNECTION_TYPE, _NAME
    env_url = os.getenv('BEMADE_SYNC_DEFAULT_URL')
    env_db = os.getenv('BEMADE_SYNC_DEFAULT_DATABASE')
    env_user = os.getenv('BEMADE_SYNC_DEFAULT_USERNAME')
    env_api_key = os.getenv('BEMADE_SYNC_DEFAULT_API_KEY')
    env_conn = os.getenv('BEMADE_SYNC_DEFAULT_CONNECTION_TYPE')
    env_name = os.getenv('BEMADE_SYNC_DEFAULT_NAME')

    # If provided via env, also persist as config parameters (except name)
    if env_url:
        ICP.set_param('bemade.sync.default_url', env_url)
    if env_db:
        ICP.set_param('bemade.sync.default_database', env_db)
    if env_user:
        ICP.set_param('bemade.sync.default_username', env_user)
    if env_conn:
        ICP.set_param('bemade.sync.default_connection_type', env_conn)
    if env_api_key:
        # Keep API key in parameters only if explicitly injected via env
        ICP.set_param('bemade.sync.default_api_key', env_api_key)

    # Resolve final defaults (env overrides > ICP defaults)
    url = env_url or ICP.get_param('bemade.sync.default_url')
    database = env_db or ICP.get_param('bemade.sync.default_database')
    username = env_user or ICP.get_param('bemade.sync.default_username')
    api_key = env_api_key or ICP.get_param('bemade.sync.default_api_key')
    connection_type = str(env_conn or ICP.get_param('bemade.sync.default_connection_type') or 'jsonrpc').strip()
    timeout = int(ICP.get_param('bemade.sync.default_timeout') or 30)
    retry_count = int(ICP.get_param('bemade.sync.default_retry_count') or 3)
    retry_delay = int(ICP.get_param('bemade.sync.default_retry_delay') or 5)

    # Create or update a default Bemade instance for immediate use in the Assign wizard
    try:
        Instance = env['odoo.to.bemade.instance'].sudo()

        # Only proceed when we have the minimum secure credentials
        if url and database and username and api_key:
            domain = [('url', '=', url), ('database', '=', database), ('username', '=', username)]
            instance = Instance.search(domain, limit=1)

            vals = {
                'name': (env_name or f"Bemade {database}").strip(),
                'url': url,
                'database': database,
                'username': username,
                'api_key': api_key,
                'connection_type': connection_type,
                'connection_timeout': timeout,
                'retry_count': retry_count,
                'retry_delay': retry_delay,
                'active': True,
            }

            if instance:
                instance.write(vals)
                _logger.info("[Bemade Sync] Updated default instance '%s' (%s/%s)", instance.name, url, database)
            else:
                instance = Instance.create(vals)
                _logger.info("[Bemade Sync] Created default instance '%s' (%s/%s)", instance.name, url, database)

            # Best-effort connection test; do not fail installation
            try:
                # Apply a temporary global socket timeout so lower-level libs (XML-RPC / OdooRPC)
                # cannot block the installation indefinitely.
                prev_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(timeout or 30)
                _logger.info("[Bemade Sync] Testing connection (type=%s, timeout=%ss)...", connection_type, timeout)
                instance.test_connection()
            except Exception as exc:  # noqa: BLE001 - broad by design for robustness during install
                _logger.warning("[Bemade Sync] Connection test failed during post-init: %s", exc)
            finally:
                # Always restore previous socket timeout
                try:
                    socket.setdefaulttimeout(prev_timeout)
                except Exception:
                    pass
        else:
            _logger.warning(
                "[Bemade Sync] Skipping default instance creation. Missing one of url/database/username/api_key. "
                "url=%s database=%s username=%s api_key=%s",
                bool(url), bool(database), bool(username), bool(api_key)
            )
    except Exception as exc:  # noqa: BLE001
        # Never break installation; just log the error
        _logger.error("[Bemade Sync] Error while creating/updating default instance: %s", exc)
