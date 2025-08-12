# Odoo to Odoo Bemade

## Overview
The `odoo_to_odoo_bemade` module extends the core synchronization framework to provide a universal connector for Bemade's Odoo instances. It adds advanced features specifically designed for Bemade's synchronization requirements, including enhanced logging, project integration, and specialized connection handling.

## Features
- **Advanced Connection Management**: Support for multiple connection types and authentication methods
- **Project Integration**: Links synchronization configurations with Odoo projects
- **Enhanced Logging System**: 
  - Multiple log levels (DEBUG, INFO, WARNING, ERROR)
  - Sensitive data masking for security
  - Long-term retention policy with AWS S3 Glacier archiving
  - Performance-optimized database indexing
- **Improved Field Mapping**: More sophisticated field mapping capabilities
- **Administrator Interface**: Advanced tools for monitoring and troubleshooting

## Technical Enhancements

### Advanced Logging
The module implements a comprehensive logging system with:
- **Log Levels**: Categorize logs by severity (DEBUG, INFO, WARNING, ERROR)
- **Data Security**: Automatic masking of sensitive information (passwords, API keys, tokens)
- **Retention Policy**: 
  - 90 days of logs kept in the database
  - Older logs archived to AWS S3 Glacier Deep Archive with 7-year retention
- **Detailed Context**: Capture full payloads, diffs, and metadata for troubleshooting

### Connection Types
Supports multiple connection methods:
- **XML-RPC**: Standard Odoo API connection
- **OdooRPC**: Using the OdooRPC library for enhanced functionality
- **REST API**: For connecting to REST-enabled Odoo instances
- **Custom Protocols**: Extensible architecture for additional protocols

### Project Integration
- Link synchronization configurations to specific projects
- Track synchronization activities within project context
- Provide project-specific dashboards and reports

## Configuration

### Setting Up Bemade Instances
1. Navigate to **Synchronization > Configuration > Bemade Instances**
2. Create a new instance with:
   - Connection details (URL, database, credentials)
   - Connection type selection
   - Advanced options for timeout, retry, etc.
3. Test the connection using the "Test Connection" button

### Configuring Synchronization Models
1. Navigate to **Synchronization > Configuration > Bemade Models**
2. Create or select models for synchronization
3. Configure detailed field mappings
4. Set synchronization rules and triggers

### Monitoring and Management
- View comprehensive logs in **Synchronization > Bemade Logs**
- Monitor queue status in **Synchronization > Bemade Queue**
- Link synchronization activities to projects

## Technical Notes
- Built on top of `odoo_to_odoo_sync` core framework
- Implements enhanced security features for sensitive data
- Provides optimized performance for large-scale synchronization
- Includes AWS S3 integration for long-term log archiving

## Requirements
- Odoo 18.0
- `odoo_to_odoo_sync` module
- `project` module
- Optional: boto3 Python library for AWS S3 integration

## License
LGPL-3.0
