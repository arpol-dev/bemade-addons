# Odoo to Odoo Bemade Customer

## Overview
The `odoo_to_odoo_bemade_customer` module provides a specialized connector for Bemade customers to securely synchronize with the central Odoo.bemade.org platform. It simplifies the configuration process and offers a streamlined experience tailored specifically for Bemade's customer environments.

## Features
- **Secure Connection**: Pre-configured secure connection to Odoo.bemade.org
- **Simplified Setup**: Automated configuration with minimal manual steps
- **Specialized Synchronization**: Optimized for Bemade's customer use cases
- **Automated Monitoring**: Built-in monitoring and error reporting
- **Customer-Specific Interface**: Simplified UI designed for end-users

## Key Components

### Sync Configuration
A centralized configuration system that:
- Automatically detects required synchronization models
- Pre-configures field mappings based on best practices
- Provides one-click setup for common synchronization scenarios
- Validates configurations to prevent common issues

### Secure Connection Management
- Handles authentication securely
- Manages API keys and credentials
- Implements proper encryption and security measures
- Provides connection health monitoring

### Specialized Logging
- Customer-focused log entries
- Simplified troubleshooting information
- Automatic reporting of critical issues
- Integration with Bemade's support systems

## Setup and Configuration

### Initial Setup
1. Install the module
2. Navigate to **Synchronization > Bemade Customer > Configuration**
3. Enter your Bemade customer credentials
4. Click "Initialize Connection" to establish the secure link

### Configuring Synchronization
1. Navigate to **Synchronization > Bemade Customer > Models**
2. Select from the list of recommended synchronization models
3. Review and adjust the pre-configured field mappings if needed
4. Activate synchronization with the "Enable" toggle

### Monitoring
- View synchronization status in **Synchronization > Bemade Customer > Dashboard**
- Check logs in **Synchronization > Bemade Customer > Logs**
- Monitor queue in **Synchronization > Bemade Customer > Queue**

## Usage Scenarios

### Initial Data Migration
- Configure models for one-time or continuous synchronization
- Use the "Initial Sync" wizard to perform bulk data transfer
- Monitor progress through the dedicated dashboard

### Ongoing Synchronization
- Automatic synchronization based on configured triggers
- Manual synchronization options for immediate updates
- Scheduled synchronization for regular data exchange

### Troubleshooting
- Use the simplified log viewer to identify issues
- Access the connection test tools to verify connectivity
- Contact Bemade support directly through the integrated support channel

## Technical Notes
- Built on top of `odoo_to_odoo_sync` core framework
- Specialized for secure connection to Odoo.bemade.org
- Implements customer-specific optimizations and simplifications
- Provides streamlined user experience for non-technical users

## Requirements
- Odoo 18.0
- `odoo_to_odoo_sync` module
- Valid Bemade customer account
- Network connectivity to Odoo.bemade.org

## License
LGPL-3.0
