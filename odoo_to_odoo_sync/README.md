# Odoo to Odoo Sync

## Overview
The `odoo_to_odoo_sync` module provides a robust foundation for bidirectional synchronization between Odoo instances. It serves as the core framework upon which more specialized synchronization modules are built.

## Features
- **Multi-Instance Support**: Connect and synchronize with multiple Odoo instances simultaneously
- **Asynchronous Synchronization**: Queue-based architecture ensures reliable data transfer without blocking operations
- **Conflict Management**: Built-in conflict detection and resolution mechanisms
- **Error Handling**: Comprehensive logging and error recovery systems
- **Monitoring Tools**: Dashboard for monitoring synchronization status and performance

## Technical Architecture

### Core Components
1. **Sync Instance**: Manages connection details and authentication for external Odoo instances
2. **Sync Model**: Defines which models should be synchronized and their mapping configuration
3. **Sync Queue**: Handles the asynchronous processing of synchronization operations
4. **Sync Log**: Records all synchronization activities for auditing and troubleshooting
5. **Sync Conflict**: Manages detected conflicts and provides resolution mechanisms
6. **Sync Manager**: Orchestrates the entire synchronization process

### Synchronization Process
1. Changes are detected through model observers
2. Sync operations are queued for processing
3. Queue processor executes operations asynchronously
4. Results are logged and conflicts are identified
5. Administrators can monitor and resolve issues through the interface

## Configuration

### Setting Up Instances
1. Navigate to **Synchronization > Configuration > Instances**
2. Create a new instance with connection details:
   - URL
   - Database
   - Username/API Key
   - Password/API Secret
3. Test the connection before proceeding

### Configuring Models for Synchronization
1. Navigate to **Synchronization > Configuration > Models**
2. Create a new sync model:
   - Select the Odoo model to synchronize
   - Choose the target instance
   - Configure field mappings
   - Set synchronization direction (bidirectional, push, or pull)

### Monitoring and Management
- View synchronization status in **Synchronization > Dashboard**
- Check logs in **Synchronization > Logs**
- Resolve conflicts in **Synchronization > Conflicts**

## Technical Notes
- Built on a queue-based architecture for reliability
- Uses Odoo's ORM hooks for change detection
- Implements proper error handling and retry mechanisms
- Provides extension points for specialized synchronization modules

## Requirements
- Odoo 18.0
- Network connectivity between Odoo instances
- Appropriate API access rights on both instances

## License
LGPL-3.0
