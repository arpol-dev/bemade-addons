# Odoo to Odoo Bemade Customer

## Overview
Complete bidirectional synchronization system for Bemade customers to securely sync with Odoo.bemade.org. Features wizards for project assignment/reception, multi-protocol support (XML-RPC, JSON-RPC, OdooRPC), and automated configuration.

## Features

### ✅ Bidirectional Sync Wizards
- **Receive Project Wizard**: `odoo.to.bemade.customer.receive.wizard`
- **Assign Project Wizard**: `odoo.to.bemade.assign.project.wizard` (server-side)
- **One-click setup**: Automated configuration with generated keys
- **Protocol selection**: Choose XML-RPC, JSON-RPC, or OdooRPC

### ✅ Multi-Protocol Support
- **XML-RPC**: Traditional XML-RPC with API key authentication
- **JSON-RPC**: JSON-based protocol with Odoo 18 API format
- **OdooRPC**: Native OdooRPC library with encrypted credentials

### ✅ Secure Authentication
- **Encrypted API keys**: AES encryption for secure storage
- **Project keys**: Unique identifiers for each sync project
- **Token generation**: Automatic API token creation and sharing

### ✅ Project Management
- **Project assignment**: Server assigns projects to clients
- **Project reception**: Client receives and configures projects
- **Key management**: Automatic key/token generation and validation

## Installation

### Prerequisites
- Odoo 17+ or 18+
- `odoo_to_odoo_sync` module (base framework)
- Network access to Odoo.bemade.org

### Installation Steps
1. Install base dependencies:
   ```bash
   pip install odoorpc  # For OdooRPC protocol
   ```

2. Install in Odoo:
   - Go to Apps → Search "odoo_to_odoo_bemade_customer"
   - Click Install

## Configuration

### Server Side (Bemade)
1. Install `odoo_to_odoo_bemade` module
2. Navigate to **Project → Bemade Sync → Assign to Client**
3. Select project and configure sync settings
4. Generate project key and API token
5. Share credentials with customer

### Client Side (Customer)
1. Install `odoo_to_odoo_bemade_customer` module
2. Navigate to **Project → Bemade Sync → Receive from Bemade**
3. Enter provided credentials:
   - Bemade server URL (default: https://odoo.bemade.org)
   - Database name
   - Username
   - API Key
   - Project Key
4. Select protocol (XML-RPC/JSON-RPC/OdooRPC)
5. Test connection and receive project

## Usage

### Using the Receive Project Wizard
1. **Open Wizard**: Project → Bemade Sync → Receive from Bemade
2. **Enter Connection Details**:
   - Server URL: https://odoo.bemade.org (or custom)
   - Database: Target database name
   - Username: Your Bemade username
   - API Key: Generated from user preferences
   - Project Key: Provided by Bemade
3. **Select Protocol**: XML-RPC, JSON-RPC, or OdooRPC
4. **Test Connection**: Validate settings before proceeding
5. **Receive Project**: Import project data and tasks

### Protocol Configuration
- **XML-RPC**: Traditional XML-RPC protocol
- **JSON-RPC**: JSON-based with Odoo 18 format: `{'scope': 'rpc', 'key': 'api_key'}`
- **OdooRPC**: Native library with automatic connection handling

### Field Mapping
- **Automatic**: Pre-configured field mappings for common models
- **Manual**: Override mappings via sync model configuration
- **Transformations**: Support for field value transformations

## Bidirectional Sync Workflow

### 1. Server Assignment
```
Bemade Server → Assign Project Wizard → Generate Keys → Share with Client
```

### 2. Client Reception
```
Client → Receive Project Wizard → Enter Credentials → Import Project → Configure Sync
```

### 3. Ongoing Synchronization
- **Automatic**: Real-time sync based on triggers
- **Manual**: Force sync via project actions
- **Scheduled**: Cron-based regular synchronization

## API Authentication Format

### Odoo 18 API Key Format
```python
# XML-RPC
{'scope': 'rpc', 'key': 'your_api_key_here'}

# JSON-RPC
{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
        "service": "common",
        "method": "login",
        "args": ["database", "username", {"scope": "rpc", "key": "api_key"}]
    }
}

# OdooRPC
odoo.login(database, username, api_key)
```

## Troubleshooting

### Common Issues
1. **Connection Failed**: Check URL, credentials, and network access
2. **Authentication Error**: Verify API key format (Odoo 18 requires scope parameter)
3. **Project Not Found**: Ensure project key is correct and project exists
4. **Protocol Error**: Try different protocol (XML-RPC/JSON-RPC/OdooRPC)

### Debug Commands
```python
# Enable debug logging
import logging
logging.getLogger('odoo.sync').setLevel(logging.DEBUG)

# Test connection programmatically
sync_instance = env['odoo.sync.instance'].search([('name', '=', 'bemade')])
sync_instance.test_connection()
```

## Project Configuration

### Project Fields Added
- **is_bemade_project**: Boolean flag for Bemade projects
- **bemade_project_key**: Unique project identifier
- **bemade_sync_enabled**: Enable/disable synchronization

### Security Access
- **User Groups**: Bemade Sync User, Bemade Sync Manager
- **Permissions**: Read, Create, Write, Delete based on role

## Development

### Extending Functionality
- **Custom Wizards**: Inherit from base wizard classes
- **Protocol Handlers**: Add new protocol support
- **Field Transformers**: Custom field value transformations
- **Conflict Resolvers**: Custom conflict resolution strategies

### Testing
```bash
# Run module tests
./odoo-bin -d your_database -u odoo_to_odoo_bemade_customer --test-enable

# Test specific wizard
env['odoo.to.bemade.customer.receive.wizard'].create({...}).action_receive_project()
```

## Support

### Getting Help
- **Logs**: Check Odoo logs and sync logs
- **Connection Test**: Use built-in connection validation
- **Support**: Contact Bemade support with sync logs

### Log Locations
- **Odoo Logs**: `/var/log/odoo/odoo.log`
- **Sync Logs**: Settings → Technical → Odoo Sync → Logs
- **Debug Mode**: Enable debug logging for detailed information

---
*Last Updated: 2025-08-16*
*Compatible with Odoo 17+ and 18+*
