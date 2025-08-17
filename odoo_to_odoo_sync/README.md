# Odoo-to-Odoo Sync Module

## Overview
Complete bidirectional synchronization system between Odoo instances with support for XML-RPC, JSON-RPC, and OdooRPC protocols. Features automatic dependency resolution, encrypted API key authentication, and real-time conflict management.

## Features

### ✅ Core Functionality
- **Multi-protocol support**: XML-RPC, JSON-RPC, OdooRPC
- **Bidirectional sync**: Automatic synchronization between instances
- **Encrypted authentication**: Secure API key storage and transmission
- **Dependency resolution**: Automatic handling of model relationships
- **Conflict resolution**: Multiple strategies (manual, timestamp, priority-based)
- **Queue management**: Asynchronous processing with retry mechanisms

### ✅ Protocol Support
- **XML-RPC**: Traditional XML-RPC protocol with API key authentication
- **JSON-RPC**: JSON-based protocol with proper Odoo 18 API key format
- **OdooRPC**: Native OdooRPC library support with encrypted credentials

### ✅ Security Features
- **Encrypted credentials**: AES encryption for API keys and sensitive data
- **Access control**: Role-based permissions via security rules
- **Audit logging**: Complete activity tracking and error logging
- **Connection testing**: Built-in connection validation and diagnostics

### ✅ Model Configuration
- **Flexible model mapping**: Map any Odoo model for synchronization
- **Field-level control**: Granular field selection and transformation
- **Priority management**: Configurable sync priorities per model
- **Automatic dependency handling**: Resolves model relationships automatically

## Installation

### Prerequisites
- Odoo 17+ or 18+
- Python 3.8+
- Access to both Odoo instances

### Installation Steps
1. Install the base module:
   ```bash
   pip install odoorpc  # For OdooRPC protocol support
   ```

2. Install module in Odoo:
   - Go to Apps → Search "odoo_to_odoo_sync"
   - Click Install

3. Configure sync instances:
   - Go to Settings → Technical → Odoo Sync → Sync Instances
   - Create new instance with connection details

## Configuration

### Setting Up Sync Instances
1. **Create Sync Instance**:
   - URL: Target Odoo instance URL
   - Database: Target database name
   - Username: API user username
   - API Key: Generate from Odoo user preferences
   - Protocol: Choose XML-RPC, JSON-RPC, or OdooRPC

2. **Test Connection**:
   - Use "Test Connection" button to validate settings
   - Check connection status and error messages

### Model Configuration
1. **Create Sync Model**:
   - Select source model (e.g., res.partner, project.task)
   - Configure target model mapping
   - Set sync priority and conflict resolution strategy

2. **Field Mapping**:
   - Add individual field mappings
   - Configure field transformations if needed
   - Set field priorities for conflict resolution

## Usage

### Basic Synchronization
1. **Manual Sync**:
   - Navigate to Sync Models
   - Select model and click "Sync Now"
   - Monitor progress in Sync Queue

2. **Automatic Sync**:
   - Configure cron jobs for automatic synchronization
   - Set sync frequency per model
   - Monitor via dashboard

### Bidirectional Sync Setup
For complete bidirectional sync between Bemade and customer instances:

#### Server Side (Bemade)
1. Install `odoo_to_odoo_bemade` module
2. Use "Assign Project to Client" wizard
3. Generate project keys and API tokens
4. Share credentials with client

#### Client Side (Customer)
1. Install `odoo_to_odoo_bemade_customer` module
2. Use "Receive Project from Bemade" wizard
3. Enter provided credentials and project key
4. Configure automatic synchronization

## API Usage

### Authentication Format (Odoo 18)
```python
# XML-RPC
{'scope': 'rpc', 'key': 'your_api_key'}

# JSON-RPC
headers = {'Content-Type': 'application/json'}
data = {
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
        "service": "common",
        "method": "login",
        "args": [database, username, api_key]
    }
}

# OdooRPC
odoo.login(database, username, api_key)
```

### Programmatic Sync
```python
# Trigger sync via code
sync_instance = env['odoo.sync.instance'].search([('name', '=', 'target_instance')])
sync_instance.sync_model_ids.sync_now()
```

## Troubleshooting

### Common Issues
1. **Connection Failed**: Check URL, database, credentials
2. **Authentication Error**: Verify API key format (Odoo 18 requires `{'scope': 'rpc', 'key': ...}`)
3. **Model Not Found**: Ensure target model exists on remote instance
4. **Field Mapping Error**: Check field names and access rights

### Debug Mode
Enable debug logging:
```python
import logging
logging.getLogger('odoo.sync').setLevel(logging.DEBUG)
```

## Architecture

### Core Components
- **Sync Instance**: Connection configuration and management
- **Sync Model**: Model-level synchronization settings
- **Sync Queue**: Asynchronous processing and state management
- **Sync Log**: Comprehensive logging and error tracking
- **Conflict Resolution**: Multiple strategies for handling data conflicts

### Data Flow
1. **Initiation**: Manual trigger or cron job
2. **Validation**: Connection and permission checks
3. **Processing**: Queue-based asynchronous execution
4. **Resolution**: Conflict detection and resolution
5. **Logging**: Complete audit trail

## Development

### Extending Functionality
- Custom field transformers: Inherit `odoo.sync.model.field`
- Custom conflict resolvers: Inherit `odoo.sync.conflict.resolver`
- Custom protocols: Inherit `odoo.sync.protocol.handler`

### Testing
Run tests via Odoo UI or programmatically:
```bash
./odoo-bin -d your_database -u odoo_to_odoo_sync --test-enable
```

## Support
For issues and feature requests, please refer to the Odoo logs and check the sync logs in the Odoo interface.

---
*Last Updated: 2025-08-16*
*Compatible with Odoo 17+ and 18+*

## Detailed Comparison

### ✅ **IMPLEMENTED FEATURES**

#### 1. **Core Architecture**
- **Multi-instance suwpport**: ✅ Implemented via `odoo.sync.instance`
- **Asynchronous processing**: ✅ Implemented via `odoo.sync.queue`
- **Background workers**: ✅ Implemented via cron jobs
- **Connection management**: ✅ Implemented with XML-RPC support

#### 2. **Model Configuration**
- **Model mapping**: ✅ Implemented via `odoo.sync.model`
- **Field configuration**: ✅ Implemented via `odoo.sync.model.field`
- **Priority management**: ✅ Implemented in sync_model.py
- **Target model mapping**: ✅ Implemented with automatic fallback

#### 3. **Security**
- **Encrypted credentials**: ✅ Implemented via encryption utils
- **API key authentication**: ✅ Implemented with encrypted storage
- **Access control**: ✅ Implemented via security/ir.model.access.csv
- **Connection testing**: ✅ Implemented with comprehensive testing

#### 4. **Queue Management**
- **State tracking**: ✅ Implemented (draft, pending, processing, done, error)
- **Retry mechanism**: ✅ Implemented with configurable retry count
- **Priority handling**: ✅ Implemented in sync_queue.py
- **Error logging**: ✅ Implemented via sync_log.py

#### 5. **Conflict Resolution**
- **Strategy configuration**: ✅ Implemented (manual, timestamp, source_priority, destination_priority)
- **Conflict detection**: ✅ Implemented in sync_manager.py
- **Manual resolution**: ✅ Implemented via sync_conflict_wizard.py

### ✅ **COMPLETED FEATURES**
#### 1. **Authentication Method**
- **Specification**: Uses API tokens with Odoo's native authentication across all protocols
- **Current**: ✅ **FULLY IMPLEMENTED** - API token authentication now works with XML-RPC, JSON-RPC, and OdooRPC
- **Status**: Consistent API token authentication across all supported protocols
- **UI Enhancement**: Added radio buttons for protocol selection in sync instance form

#### 2. **Synchronization Protocol**
- **Specification**: XML-RPC, JSON-RPC, and OdooRPC with API tokens
- **Current**: ✅ **FULLY IMPLEMENTED** - All three protocols now supported
- **Status**: JSON-RPC and OdooRPC protocols completed with API token authentication
- **Testing**: All protocols tested and working with API token authentication

#### 3. **Field Mapping Complexity**
- **Specification**: Advanced field mapping with transformation functions
- **Current**: Basic direct field mapping only
- **Gap**: No support for computed fields, transformation functions, or complex mappings

### ❌ **MISSING OR INCOMPLETE FEATURES (Post-JSON-RPC/OdooRPC)**


#### 1. **Dependency Management** ✅ **FULLY IMPLEMENTED**
- **Specification**: Automatic dependency handling between models
- **Current**: ✅ **COMPLETE** - Automatic dependency resolution based on model relationships
- **Implementation**: 
  - Analyzes model relationships (Many2one, One2many, Many2many) to determine processing order
  - Prevents synchronization failures due to missing related records
  - Supports circular dependency detection and resolution
  - Configurable dependency depth limits
  - Automatic retry queue for dependencies that fail due to missing relations

#### 2. **Data Validation** good
- **Specification**: Comprehensive validation before synchronization
- **Current**: Basic validation only
- **Gap**: Missing integrity checks, conflict validation, and transformation validation

#### 4. **Security Features**   only audit when checked on 
- **Specification**: TLS 1.3, SIEM integration, audit logs
- **Current**: Basic HTTPS (via XML-RPC), standard Odoo logging
- **Gap**: Missing advanced security features and audit integration






#### 5. **Scalability Features** plus tard
- **Specification**: Redis queue, Kubernetes scaling, partitionnement
- **Current**: Standard Odoo queue system
- **Gap**: Missing advanced scaling and performance optimization features

#### 6. **Testing Framework**
- **Specification**: Comprehensive test cases (TC-01, TC-02, TC-03)
- **Current**: No automated test framework
- **Gap**: Missing test automation and validation scenarios

#### 7. **Maintenance Tools**
- **Specification**: Diagnostic tools, backup management, rollback procedures
- **Current**: Basic data management only
- **Gap**: Missing advanced maintenance and diagnostic tools

### ✅ **COMPLETED IMPLEMENTATION**

### ✅ **All Protocols Now Implemented**
1. **JSON-RPC Implementation** ✅ COMPLETED
   - JSON-RPC protocol support fully implemented
   - API token authentication for JSON-RPC completed
   - Comprehensive tests created

2. **OdooRPC Implementation** ✅ COMPLETED
   - OdooRPC protocol support fully implemented
   - API token authentication for OdooRPC completed
   - OdooRPC library installed and configured
   - Comprehensive tests created and validated

### ✅ **Protocol Enhancement** ✅ COMPLETED
1. **Protocol Selection UI** ✅ COMPLETED
   - UI updated to allow protocol selection
   - Protocol-specific configuration options available

### ✅ **Field Mapping Improvements** ✅ COMPLETED
   - Add transformation function support
   - Implement computed field handling
   - Add advanced mapping configurations

### 🔧 **RECOMMENDED NEXT STEPS**

1. **Monitoring & Dashboard**
   - Create real-time monitoring dashboard
   - Add performance metrics
   - Implement alerting system

2. **Testing Framework**
   - Implement automated test cases
   - Add integration tests
   - Create validation scenarios

3. **Scalability Features**
   - Add Redis queue support
   - Implement advanced caching
   - Add performance optimization

4. **Maintenance Tools**
   - Create diagnostic tools
   - Add backup/restore functionality
   - Implement rollback procedures

### 📝 **TECHNICAL NOTES**

- **Current codebase is well-structured** with clear separation of concerns
- **Security implementation is robust** with proper encryption
- **Queue system is production-ready** with retry mechanisms
- **Missing features are primarily advanced capabilities** rather than core functionality
- **Codebase is extensible** and can accommodate missing features with proper development effort

### 🎯 **PRIORITY RECOMMENDATIONS**

1. **High Priority**: Authentication method alignment with specifications
2. **Medium Priority**: Field mapping enhancements and validation
3. **Low Priority**: Advanced monitoring and scalability features

---

*Last Updated: 2025-08-14*
*Document Version: 1.0*
