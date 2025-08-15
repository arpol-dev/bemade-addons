# Copyright 2025 Codeium
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Management System.

This module implements the core synchronization logic and conflict resolution
strategies. It manages the overall synchronization process, including queuing
operations, handling retries, and ensuring data consistency across instances.
"""

import json
import logging
import traceback
import base64
from datetime import datetime, timedelta
import xmlrpc.client

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class SyncConflictException(Exception):
    """Exception raised when a synchronization conflict is detected.
    
    This exception is raised when the synchronization process encounters
    conflicting changes between source and destination instances that
    cannot be automatically resolved based on the current conflict
    resolution strategy.
    """
    pass

class OdooSyncManager(models.Model):
    """Manages synchronization operations between Odoo instances.

    This class is responsible for orchestrating the synchronization process,
    including:
    - Managing synchronization queues
    - Handling conflict resolution
    - Coordinating data transfer between instances
    - Monitoring synchronization status
    - Implementing retry mechanisms
    - Logging synchronization events

    The synchronization process is configurable through various strategies
    and can be customized based on specific business needs.
    """
    _name = 'odoo.sync.manager'
    _description = 'Odoo Sync Manager'

    name = fields.Char(
        string='Name',
        default='Global Configuration',
        required=True
    )
    
    conflict_resolution_strategy = fields.Selection([
        ('manual', 'Manual Resolution'),
        ('timestamp', 'Newest Wins'),
        ('source_priority', 'Source Instance Wins'),
        ('destination_priority', 'Destination Instance Wins')
    ], string='Conflict Resolution Strategy', default='manual',
       help='Default strategy for resolving synchronization conflicts')
    


    def _get_sync_models(self):
        """Récupère tous les modèles actifs à synchroniser"""
        return self.env['odoo.sync.model'].search([('active', '=', True)])

    def _queue_sync(self, record, operation, fields_list=None):
        """Queue a synchronization operation.
        
        This method implements the "Create SyncRecord" step in the synchronization sequence diagram.
        It creates a queue entry for the specified record and operation.
        
        Args:
            record: The record to synchronize
            operation: The operation type ('create', 'write', 'unlink')
            fields_list: Optional list of fields to synchronize (for write operations)
            
        Returns:
            odoo.sync.queue: The created queue entry or False if failed
        """
        try:
            _logger.debug(f"[SYNC MANAGER] Create SyncRecord: {operation} on {record._name} (ID: {record.id})")
            
            # Check if the model is configured for synchronization
            sync_model = self.env['odoo.sync.model'].sudo().search([
                ('model_id.model', '=', record._name),
                ('active', '=', True)
            ], limit=1)
            
            if not sync_model:
                _logger.debug(f"[SYNC MANAGER] Model {record._name} not configured for sync")
                return False
                
            # Prepare data for synchronization
            data = {}
            
            # For create/write operations, get all relevant data
            if operation in ['create', 'write']:
                # Get all model fields
                model_fields = self.env[record._name]._fields
                
                # Filter fields to synchronize if a list is provided
                if fields_list:
                    fields_to_sync = [f for f in fields_list if f in model_fields]
                else:
                    fields_to_sync = list(model_fields.keys())
                
                # Add fields configured for synchronization
                if sync_model.field_ids:
                    sync_fields = sync_model.field_ids.mapped('name')
                    fields_to_sync = [f for f in fields_to_sync if f in sync_fields]
                
                # Get field values
                for field in fields_to_sync:
                    if field in model_fields:
                        value = record[field]
                        data[field] = self._prepare_data_for_json(value)
                
                # Add ID for update operations
                data['id'] = record.id
                
            # For delete operations, we just need the ID
            elif operation == 'unlink':
                data['id'] = record.id
            
            # Create the queue entry
            queue_entry = self.env['odoo.sync.queue'].create({
                'model_id': sync_model.id,
                'record_id': record.id,
                'operation': operation,
                'state': 'pending',
                'priority': sync_model.priority or 10,
                'data': json.dumps(data)
            })
            
            _logger.debug(f"[SYNC MANAGER] Created queue entry {queue_entry.id} for {operation} operation on {record._name} (ID: {record.id})")
            
            return queue_entry
            
        except Exception as e:
            _logger.error(f"[SYNC MANAGER] Error creating SyncRecord: {str(e)}")
            _logger.error(traceback.format_exc())
            _logger.error(traceback.format_exc())

    def _process_sync_queue(self):
        """Process the synchronization queue following the sequence diagram.
        
        This method is the entry point for the cron job that processes the queue.
        It delegates to the SyncQueue model's _process_sync_queue method to follow
        the exact sequence in the diagram.
        """
        _logger.debug("[SYNC MANAGER] [SEQUENCE STEP] Starting sync queue processing")
        _logger.debug("[SYNC MANAGER] [SEQUENCE STEP] Delegating to SyncQueue._process_sync_queue")
        result = self.env['odoo.sync.queue']._process_sync_queue()
        _logger.debug("[SYNC MANAGER] [SEQUENCE STEP] Sync queue processing completed")
        return result

    def _process_dequeued_item(self, queue_item):
        """Process a dequeued sync queue item.
        
        This method follows the exact sequence diagram flow:
        1. Prepare payload
        2. Transform/validate
        3. Apply changes
        4. Receive ACK/NACK
        5. Handle success or error paths
        
        Args:
            queue_item: The dequeued sync queue item to process
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Processing dequeued item {queue_item.id} for {queue_item.operation} operation on model {queue_item.model_id.model_id.model if queue_item.model_id and queue_item.model_id.model_id else 'unknown'}")
        
        try:
            # Get the sync model
            sync_model = queue_item.model_id
            if not sync_model:
                _logger.error(f"[SYNC MANAGER] No sync model found for queue item {queue_item.id}")
                return False
                
            # Get the remote instance
            remote_instance = sync_model.instance_id
            if not remote_instance:
                _logger.error(f"[SYNC MANAGER] No remote instance found for sync model {sync_model.name}")
                return False
                
            # Parse the data
            data = json.loads(queue_item.data)
            
            # Prepare the payload (Step 1 in sequence diagram)
            _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Preparing payload for queue item {queue_item.id}")
            payload = self._prepare_sync_data(queue_item, data)
            
            # Transform/validate the payload (Step 2 in sequence diagram)
            _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Transforming/validating payload for queue item {queue_item.id}")
            # Validate the payload structure and data types
            if not isinstance(payload, dict):
                error_msg = f"Invalid payload format for queue item {queue_item.id}. Expected dict, got {type(payload)}"
                _logger.error(f"[SYNC MANAGER] {error_msg}")
                queue_item.increment_retry(error_msg)
                return False
            
            # Validate required fields are present
            required_fields = ['id', 'model']
            for field in required_fields:
                if field not in payload:
                    error_msg = f"Missing required field '{field}' in payload for queue item {queue_item.id}"
                    _logger.error(f"[SYNC MANAGER] {error_msg}")
                    queue_item.increment_retry(error_msg)
                    return False
            
            # Validate operation is supported
            valid_operations = ['create', 'write', 'unlink']
            if queue_item.operation not in valid_operations:
                error_msg = f"Invalid operation '{queue_item.operation}' for queue item {queue_item.id}. Must be one of {valid_operations}"
                _logger.error(f"[SYNC MANAGER] {error_msg}")
                queue_item.increment_retry(error_msg)
                return False
            
            # Apply changes to remote instance (Step 3 in sequence diagram)
            _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Applying changes to remote instance for queue item {queue_item.id}")
            result = self._apply_sync_to_remote(remote_instance, queue_item.operation, sync_model.model_id.model, payload)
            
            # Handle result (Step 4 & 5 in sequence diagram)
            if result.get('success'):
                # Process ACK (Step 4 in sequence diagram)
                _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Received ACK for queue item {queue_item.id}")
                self._handle_sync_ack(queue_item, result)
                return True
            else:
                # Process NACK (Step 4 in sequence diagram)
                error_message = result.get('error', 'Unknown error')
                _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Received NACK for queue item {queue_item.id}: {error_message}")
                self._handle_sync_nack(queue_item, error_message)
                return False
            
        except xmlrpc.client.Fault as e:
            # Step 4: NACK received (implicit in RPC fault)
            error_msg = str(e)
            _logger.error(f"[SYNC MANAGER] [SEQUENCE STEP] Received NACK from remote instance: {error_msg}")
            
            # Check if this is a potential conflict (record not found or modified)
            if "Record does not exist" in error_msg and queue_item.operation in ['write', 'unlink']:
                _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Potential conflict detected: {error_msg}")
                try:
                    # Try to get the remote record state
                    remote_data = None
                    data = json.loads(queue_item.data)
                    model_name = queue_item.model_id.model_id.model
                    remote_instance = queue_item.model_id.instance_id
                    
                    if 'id' in data:
                        # Try to search for the record by other criteria
                        domain = []
                        # Use name field if available
                        if 'name' in data:
                            domain.append(('name', '=', data.get('name')))
                        # Use code/reference field if available
                        if 'code' in data:
                            domain.append(('code', '=', data.get('code')))
                        # Use other unique identifiers if available
                        
                        if domain:
                            # Connect to remote instance
                            url = remote_instance.url
                            db = remote_instance.database
                            username = remote_instance.username
                            password = remote_instance.password
                            
                            # Connect to XML-RPC endpoint
                            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
                            models_api = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
                            
                            # Authenticate
                            uid = common.authenticate(db, username, password, {})
                            if uid:
                                remote_ids = models_api.execute_kw(
                                    db, uid, password,
                                    model_name, 'search',
                                    [domain]
                                )
                                if remote_ids:
                                    remote_data_list = models_api.execute_kw(
                                        db, uid, password,
                                        model_name, 'read',
                                        [remote_ids[0], list(data.keys())]
                                    )
                                    if remote_data_list:
                                        remote_data = remote_data_list[0]
                    
                    # Create conflict record
                    if remote_data:
                        # Add model info to data for conflict resolution
                        local_data = data.copy()
                        local_data['model'] = model_name
                        remote_data['model'] = model_name
                        
                        self._handle_sync_conflict(queue_item, local_data, remote_data)
                    else:
                        # No remote data found, just mark as error
                        queue_item.increment_retry(error_msg)
                except Exception as conflict_e:
                    _logger.error(f"[SYNC MANAGER] Error during conflict handling: {str(conflict_e)}")
                    _logger.error(traceback.format_exc())
                    queue_item.increment_retry(f"Conflict handling error: {str(conflict_e)}")
            else:
                # Not a conflict, just a regular error
                queue_item.increment_retry(error_msg)
                
            return False
            
        except Exception as e:
            _logger.error(f"[SYNC MANAGER] Unexpected error processing queue item: {str(e)}")
            _logger.error(traceback.format_exc())
            queue_item.increment_retry(str(e))
            return False
            
    def _handle_sync_ack(self, queue_item, result):
        """Handle successful synchronization (ACK received).
        
        This method implements the "Success Path" in the synchronization sequence diagram.
        It marks the queue item as successful and creates a success log entry.
        
        Args:
            queue_item: The queue item that was successfully processed
            result: The result data from the remote operation
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Handling ACK for queue item {queue_item.id} - Success Path")
        
        # Mark as done
        queue_item.mark_success()
        
        # Create success log
        sync_model = queue_item.model_id
        remote_instance = sync_model.instance_id
        model_name = sync_model.model_id.model
        
        self.env['odoo.sync.log'].create({
            'queue_id': queue_item.id,
            'state': 'success',
            'message': f"Synchronisation réussie: {queue_item.operation} sur {model_name} vers {remote_instance.name}"
        })
        
        return True
        
    def _handle_sync_nack(self, queue_item, error_message):
        """Handle failed synchronization (NACK received).
        
        This method implements part of the "Error Path" in the synchronization sequence diagram.
        It increments the retry count and creates an error log entry.
        
        Args:
            queue_item: The queue item that failed to process
            error_message: The error message from the remote operation
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Handling NACK for queue item {queue_item.id} - Error Path: {error_message}")
        
        # Increment retry count
        queue_item.increment_retry(error_message)
        
        # Create error log
        self.env['odoo.sync.log'].create({
            'queue_id': queue_item.id,
            'state': 'error',
            'message': f"Erreur de synchronisation: {error_message}"
        })
        
        return True

    def _check_dependencies(self, queue_item):
        """Check if all dependencies are satisfied for this queue item.
        
        Args:
            queue_item: The queue item to check dependencies for
            
        Returns:
            bool: True if dependencies are satisfied, False otherwise
        """
        try:
            resolver = self.env['odoo.sync.dependency.resolver']
            return resolver.resolve_missing_dependencies(queue_item)
        except Exception as e:
            _logger.error(f"[SYNC MANAGER] Error checking dependencies for queue item {queue_item.id}: {str(e)}")
            return True  # Allow processing to continue if dependency check fails

    def _handle_missing_dependency(self, queue_item, error_message):
        """Handle missing dependency during synchronization.
        
        Args:
            queue_item: The queue item with missing dependencies
            error_message: The error message indicating missing dependencies
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Handling missing dependency for queue item {queue_item.id}")
        
        # Increment retry count with dependency-specific handling
        queue_item.write({
            'retry_count': queue_item.retry_count + 1,
            'next_retry': fields.Datetime.now() + timedelta(minutes=5),  # Longer delay for dependencies
            'error_message': f"Missing dependency: {error_message}"
        })
        
        # Create dependency-specific log
        self.env['odoo.sync.log'].create({
            'queue_id': queue_item.id,
            'state': 'error',
            'message': f"Missing dependency detected: {error_message}"
        })
        
        return True

    def update_model_dependencies(self, model_sync_ids=None):
        """Update dependency information for synchronized models.
        
        Args:
            model_sync_ids: List of model sync IDs to analyze. If None, analyzes all active models.
        """
        if model_sync_ids is None:
            model_sync_ids = self.env['odoo.sync.model'].search([('active', '=', True)]).ids
        
        if not model_sync_ids:
            return
            
        try:
            resolver = self.env['odoo.sync.dependency.resolver']
            analysis = resolver.analyze_model_dependencies(model_sync_ids)
            
            # Log dependency analysis results
            _logger.info(f"[SYNC MANAGER] Updated dependencies for {len(model_sync_ids)} models")
            if analysis['cycles']:
                _logger.warning(f"[SYNC MANAGER] Detected circular dependencies: {analysis['cycles']}")
                
        except Exception as e:
            _logger.error(f"[SYNC MANAGER] Error updating model dependencies: {str(e)}")
        
    def _handle_sync_conflict(self, queue_item, local_data, remote_data):
        """Handle synchronization conflict.
        
        This method implements the conflict handling branch of the "Error Path" in the sequence diagram.
        It creates a conflict record and marks the queue item as conflicted.
        
        Args:
            queue_item: The queue item that encountered a conflict
            local_data: The local data that was being synchronized
            remote_data: The conflicting remote data
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Handling conflict for queue item {queue_item.id} - Conflict Path")
        
        # Get the conflict resolution strategy from the remote instance
        remote_instance = queue_item.model_id.instance_id
        strategy = remote_instance.conflict_resolution_strategy if remote_instance else \
                  self.env['ir.config_parameter'].sudo().get_param(
                      'odoo_to_odoo_sync.default_conflict_strategy', 'manual')
        
        # Create conflict record
        conflict = self.env['odoo.sync.conflict'].create({
            'queue_id': queue_item.id,
            'model_id': queue_item.model_id.id,
            'record_id': queue_item.record_id,
            'local_data': json.dumps(local_data),
            'remote_data': json.dumps(remote_data),
            'state': 'pending',
            'resolution_strategy': strategy
        })
        
        # Mark queue item as conflicted
        queue_item.write({
            'state': 'conflict',
            'conflict_id': conflict.id
        })
        
        # Create conflict log
        self.env['odoo.sync.log'].create({
            'queue_id': queue_item.id,
            'state': 'conflict',
            'message': f"Conflit détecté et enregistré pour résolution manuelle"
        })
        
        return True

            
    def _apply_sync_to_remote(self, remote_instance, operation, model_name, data):
        """Apply synchronization changes to the remote instance.
        
        This method implements the "Apply Changes" step in the synchronization sequence diagram.
        It sends the prepared data to the remote instance via XML-RPC.
        
        Args:
            remote_instance: The remote instance to connect to
            operation: The operation type ('create', 'write', 'unlink')
            model_name: The name of the model to operate on
            data: The data to send to the remote instance
            
        Returns:
            dict: A result dictionary with success flag and any returned data or error message
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Applying {operation} on {model_name} to remote instance {remote_instance.name}")
        
        try:
            # Get connection to remote instance
            url = remote_instance.url
            db = remote_instance.database
            username = remote_instance.username
            password = remote_instance.password
            
            # Connect to XML-RPC endpoint
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
            models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
            
            # Authenticate
            uid = common.authenticate(db, username, password, {})
            if not uid:
                return {'success': False, 'error': 'Authentication failed'}
            
            # Execute the operation
            result = None
            if operation == 'create':
                _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Creating record in {model_name} with data: {data}")
                record_id = models.execute_kw(db, uid, password, model_name, 'create', [data], {'context': {'no_sync': True}})
                result = {'success': True, 'record_id': record_id}
                
            elif operation == 'write':
                _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Updating record {data.get('id')} in {model_name}")
                record_id = data.pop('id', False)
                if not record_id:
                    return {'success': False, 'error': 'No ID provided for write operation'}
                
                try:
                    # First try direct ID lookup
                    success = models.execute_kw(db, uid, password, model_name, 'write', [[record_id], data], {'context': {'no_sync': True}})
                    result = {'success': success}
                except xmlrpc.client.Fault as fault:
                    # If record not found by ID, try to find it by name
                    if "Record does not exist" in fault.faultString and 'name' in data:
                        _logger.debug(f"[SYNC MANAGER] Record {record_id} not found, trying lookup by name: {data.get('name')}")
                        # Search for record with exact name match
                        domain = [('name', '=', data.get('name'))]
                        record_ids = models.execute_kw(db, uid, password, model_name, 'search', [domain])
                        
                        if record_ids:
                            remote_id = record_ids[0]
                            _logger.debug(f"[SYNC MANAGER] Found record by name, remote ID: {remote_id}")
                            # Update the record using the found ID
                            success = models.execute_kw(db, uid, password, model_name, 'write', [[remote_id], data], {'context': {'no_sync': True}})
                            result = {'success': success, 'mapped_id': remote_id}
                        else:
                            # No record found by name either
                            raise xmlrpc.client.Fault(fault.faultCode, 
                                f"Record not found by ID ({record_id}) or name ({data.get('name')})")
                    else:
                        # Re-raise the original fault if it's not a 'record not found' error
                        # or if we don't have a name to search with
                        raise
                
            elif operation == 'unlink':
                _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Deleting record {data.get('id')} from {model_name}")
                record_id = data.get('id', False)
                if not record_id:
                    return {'success': False, 'error': 'No ID provided for unlink operation'}
                    
                success = models.execute_kw(db, uid, password, model_name, 'unlink', [[record_id]], {'context': {'no_sync': True}})
                result = {'success': success}
                
            else:
                return {'success': False, 'error': f"Unknown operation: {operation}"}
                
            _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Remote operation successful: {result}")
            return result
            
        except xmlrpc.client.Fault as fault:
            error_msg = f"XML-RPC Fault: {fault.faultCode}: {fault.faultString}"
            _logger.error(f"[SYNC MANAGER] {error_msg}")
            
            # Check for conflict indicators in the error message
            if 'concurrent' in fault.faultString.lower() or 'conflict' in fault.faultString.lower():
                return {'success': False, 'error': error_msg, 'conflict': True}
            return {'success': False, 'error': error_msg}
            
        except Exception as e:
            error_msg = f"Error applying sync to remote: {str(e)}"
            _logger.error(f"[SYNC MANAGER] {error_msg}")
            _logger.error(traceback.format_exc())
            return {'success': False, 'error': error_msg}



            

    def _prepare_data_for_json(self, data):
        """Prépare les données pour la sérialisation JSON en convertissant les types non-sérialisables"""
        if not data:
            return {}
            
        # If data is a string, return it directly
        if isinstance(data, str):
            return data
            
        # If data is a primitive type that's JSON serializable, return it directly
        if isinstance(data, (int, float, bool, type(None))):
            return data
            
        result = {}
        # Only try to iterate if data is a dict
        if isinstance(data, dict):
            for key, value in data.items():
                # Traitement des types binaires (bytes)
                if isinstance(value, bytes):
                    try:
                        # Convertir les données binaires en chaîne base64
                        result[key] = base64.b64encode(value).decode('utf-8')
                    except Exception as e:
                        _logger.warning(f"[SYNC MANAGER] Impossible de convertir le champ binaire {key}: {str(e)}")
                        result[key] = None
                # Traitement des tuples (souvent utilisés pour les relations many2one)
                elif isinstance(value, tuple) and len(value) == 2:
                    # Stocker uniquement l'ID et le nom pour les relations
                    result[key] = {'id': value[0], 'name': value[1]}
                # Traitement des listes (souvent utilisées pour les relations one2many/many2many)
                elif isinstance(value, list) and all(isinstance(item, tuple) and len(item) == 2 for item in value):
                    # Convertir les listes de tuples en listes de dictionnaires
                    result[key] = [{'id': item[0], 'name': item[1]} for item in value]
                # Traitement des dates et datetimes
                elif hasattr(value, 'isoformat'):
                    result[key] = value.isoformat()
                # Recursively process nested dictionaries
                elif isinstance(value, dict):
                    result[key] = self._prepare_data_for_json(value)
                # Recursively process lists of non-tuple items
                elif isinstance(value, list):
                    result[key] = [self._prepare_data_for_json(item) for item in value]
                # Pour les autres types, les laisser tels quels s'ils sont sérialisables
                else:
                    result[key] = value
        
        return result

    def _detect_conflict_type(self, local_data, remote_data):
        """Détecte et catégorise le type de conflit entre données locales et distantes.
        
        Args:
            local_data: Données locales (dict)
            remote_data: Données distantes (dict)
            
        Returns:
            tuple: (type_conflit, champs_conflit)
                type_conflit: 'version', 'data', 'relation' ou None
                champs_conflit: liste des champs en conflit
        """
        conflict_type = None
        conflict_fields = []
        
        # Vérifier si les deux enregistrements existent et ont été modifiés
        local_write_date = local_data.get('write_date')
        remote_write_date = remote_data.get('write_date')
        
        if local_write_date and remote_write_date:
            # Conflit de version: les deux côtés ont été modifiés depuis la dernière synchronisation
            try:
                local_date = fields.Datetime.from_string(local_write_date)
                remote_date = fields.Datetime.from_string(remote_write_date)
                
                # Si les dates sont différentes, il y a potentiellement un conflit
                if local_date and remote_date and abs((local_date - remote_date).total_seconds()) > 1:  # Tolérance d'une seconde
                    conflict_type = 'version'
            except Exception as e:
                _logger.warning(f"Erreur lors de la comparaison des dates: {str(e)}")
                # En cas d'erreur, considérer qu'il y a un conflit de version
                conflict_type = 'version'
            
            # Identifier les champs modifiés des deux côtés, même sans conflit de version
            for field, local_value in local_data.items():
                if field in remote_data and local_value != remote_data[field]:
                    # Exclure les champs système
                    if field not in ['id', 'write_date', 'create_date', 'write_uid', 'create_uid', '__last_update']:
                        conflict_fields.append(field)
                        
            # Si des champs sont en conflit, c'est un conflit de données
            if conflict_fields:
                conflict_type = 'data'
                
                # Vérifier s'il s'agit d'un conflit de relations
                relation_conflict = False
                for field in conflict_fields:
                    local_value = local_data.get(field)
                    remote_value = remote_data.get(field)
                    
                    # Détecter les relations (many2one, one2many, many2many)
                    if isinstance(local_value, dict) and 'id' in local_value:
                        relation_conflict = True
                        break
                    elif isinstance(local_value, list) and all(isinstance(item, dict) and 'id' in item for item in local_value if isinstance(item, dict)):
                        relation_conflict = True
                        break
                
                if relation_conflict:
                    conflict_type = 'relation'
        
        return conflict_type, conflict_fields

    def _handle_conflict(self, local_data, remote_data, strategy=None):
        """Gestion des conflits selon la stratégie configurée"""
        # Use the provided strategy or fall back to system parameter
        if strategy is None:
            strategy = self.env['ir.config_parameter'].sudo().get_param(
                    'odoo_to_odoo_sync.default_conflict_strategy')
        _logger.debug(f'Résolution de conflit avec stratégie: {strategy}')
        
        # Détecter le type de conflit
        conflict_type, conflict_fields = self._detect_conflict_type(local_data, remote_data)
        _logger.debug(f'Type de conflit détecté: {conflict_type}, champs: {conflict_fields}')
        
        if not conflict_type or not conflict_fields:
            # Pas de conflit réel, utiliser la stratégie globale
            if strategy == 'timestamp':
                return self._resolve_by_timestamp(local_data, remote_data)
            elif strategy == 'source_priority':
                return local_data
            elif strategy == 'destination_priority':
                return remote_data
            else:  # manual
                return self._flag_for_manual_resolution(local_data, remote_data)
        
        # Résoudre le conflit champ par champ selon les stratégies configurées
        result = local_data.copy()
        
        # Récupérer le modèle synchronisé
        model_name = local_data.get('model')
        if not model_name:
            return self._flag_for_manual_resolution(local_data, remote_data)
            
        sync_model = self.env['odoo.sync.model'].sudo().search([('model_id.model', '=', model_name)], limit=1)
        if not sync_model:
            return self._flag_for_manual_resolution(local_data, remote_data)
        
        # Parcourir les champs en conflit
        for field in conflict_fields:
            # Récupérer la stratégie de conflit pour ce champ
            field_config = sync_model.field_ids.filtered(lambda f: f.name == field)
            if not field_config:
                # Champ non configuré, utiliser la stratégie globale
                if strategy == 'timestamp':
                    result[field] = self._resolve_field_by_timestamp(field, local_data, remote_data)
                elif strategy == 'source_priority':
                    result[field] = local_data[field]
                elif strategy == 'destination_priority':
                    result[field] = remote_data[field]
                else:  # manual
                    # Si au moins un champ nécessite une résolution manuelle, tout le conflit est manuel
                    return self._flag_for_manual_resolution(local_data, remote_data)
            else:
                # Utiliser la stratégie configurée pour ce champ
                field_strategy = field_config.conflict_strategy
                if field_strategy == 'source_wins':
                    result[field] = local_data[field]
                elif field_strategy == 'dest_wins':
                    result[field] = remote_data[field]
                elif field_strategy == 'newest':
                    result[field] = self._resolve_field_by_timestamp(field, local_data, remote_data)
                else:  # manual
                    # Si au moins un champ nécessite une résolution manuelle, tout le conflit est manuel
                    return self._flag_for_manual_resolution(local_data, remote_data)
        
        return result

    def _resolve_field_by_timestamp(self, field, local_data, remote_data):
        """Résout un conflit de champ spécifique en utilisant l'horodatage
        
        Args:
            field: Nom du champ en conflit
            local_data: Données locales
            remote_data: Données distantes
            
        Returns:
            La valeur du champ la plus récente
        """
        local_date = fields.Datetime.from_string(local_data.get('write_date', '')) if local_data.get('write_date') else None
        remote_date = fields.Datetime.from_string(remote_data.get('write_date', '')) if remote_data.get('write_date') else None
        
        if local_date and remote_date:
            return local_data[field] if local_date > remote_date else remote_data[field]
        elif local_date:
            return local_data[field]
        elif remote_date:
            return remote_data[field]
        else:
            # Si pas d'horodatage, utiliser la valeur locale par défaut
            return local_data[field]

    def _resolve_by_timestamp(self, local, remote):
        """Résout un conflit en utilisant l'horodatage"""
        local_date = fields.Datetime.from_string(local.get('write_date', '')) if local.get('write_date') else None
        remote_date = fields.Datetime.from_string(remote.get('write_date', '')) if remote.get('write_date') else None
        
        if local_date and remote_date:
            return local if local_date > remote_date else remote
        elif local_date:
            return local
        elif remote_date:
            return remote
        else:
            # Si pas d'horodatage, utiliser les données locales par défaut
            return local

    def _flag_for_manual_resolution(self, local, remote):
        """Marque un conflit pour résolution manuelle"""
        self.env['odoo.sync.conflict'].create({
            'local_data': json.dumps(local),
            'remote_data': json.dumps(remote),
            'model_name': local.get('model', 'unknown'),
            'record_id': local.get('id', 0),
            'state': 'pending'
        })
        raise SyncConflictException('Conflit nécessitant une résolution manuelle')
        
    def _prepare_sync_data(self, queue_item, data):
        """Prépare les données pour l'envoi vers l'instance distante
        
        Cette méthode transforme les données JSON-sérialisées en format compatible
        avec l'API Odoo de l'instance distante, en appliquant les mappings avancés.
        """
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Preparing sync data for queue item {queue_item.id} - Payload Preparation")
        result = {}
        
        # Get the sync model from the queue item
        sync_model = queue_item.model_id
        if not sync_model:
            _logger.error(f"[SYNC MANAGER] No sync model found for queue item {queue_item.id}")
            return data
        
        # Get the original record for advanced mapping
        record = self.env[sync_model.model_id.model].browse(queue_item.record_id)
        if not record.exists():
            _logger.error(f"[SYNC MANAGER] Record {queue_item.record_id} not found in model {sync_model.model_id.model}")
            return data
        
        # Get all configured field mappings
        field_mappings = sync_model.field_ids
        
        # Supprimer les champs système et les champs non synchronisés
        excluded_fields = ['id', 'write_date', 'create_date', 'write_uid', 'create_uid', '__last_update']
        
        # For write and unlink operations, we need to keep the ID
        if queue_item.operation in ['write', 'unlink'] and 'id' in data:
            result['id'] = data['id']
        
        # Process each field mapping
        for field_mapping in field_mappings:
            if not field_mapping.active:
                continue
                
            field_name = field_mapping.field_id.name
            target_field = field_mapping.target_field or field_name
            
            try:
                value = self._apply_field_mapping(field_mapping, record, data.get(field_name))
                if value is not None:
                    result[target_field] = value
                    
            except Exception as e:
                _logger.error(f"[SYNC MANAGER] Error applying mapping for field {field_name}: {str(e)}")
                if field_mapping.required:
                    raise
                continue
        
        _logger.debug(f"[SYNC MANAGER] [SEQUENCE STEP] Prepared sync data for queue item {queue_item.id}: {result}")
        return result

    def _apply_field_mapping(self, field_mapping, record, original_value):
        """Apply advanced field mapping based on mapping type.
        
        Args:
            field_mapping: The field mapping configuration
            record: The source record being synchronized
            original_value: The original field value
            
        Returns:
            The transformed value for synchronization
        """
        mapping_type = field_mapping.mapping_type
        
        if mapping_type == 'direct':
            # Direct mapping - return value as-is
            return original_value
            
        elif mapping_type == 'function':
            # Function mapping - execute specified function
            if not field_mapping.mapping_function:
                _logger.warning(f"[SYNC MANAGER] Function mapping requested but no function specified for field {field_mapping.name}")
                return original_value
                
            try:
                # Parse function name - can be model.method_name or just method_name
                func_name = field_mapping.mapping_function
                if '.' in func_name:
                    model_name, method_name = func_name.split('.', 1)
                    model = self.env[model_name]
                    if hasattr(model, method_name):
                        method = getattr(model, method_name)
                        return method(record, original_value)
                    else:
                        _logger.error(f"[SYNC MANAGER] Method {method_name} not found in model {model_name}")
                        return original_value
                else:
                    # Try to find method on the record's model
                    if hasattr(record, func_name):
                        method = getattr(record, func_name)
                        return method(original_value)
                    else:
                        _logger.error(f"[SYNC MANAGER] Method {func_name} not found on record")
                        return original_value
                        
            except Exception as e:
                _logger.error(f"[SYNC MANAGER] Error executing function mapping for field {field_mapping.name}: {str(e)}")
                if field_mapping.required:
                    raise
                return original_value
                
        elif mapping_type == 'computed':
            # Computed mapping - evaluate expression
            if not field_mapping.mapping_expression:
                _logger.warning(f"[SYNC MANAGER] Computed mapping requested but no expression specified for field {field_mapping.name}")
                return original_value
                
            try:
                # Create safe evaluation context
                context = {
                    'record': record,
                    'value': original_value,
                    'env': self.env,
                    'datetime': __import__('datetime'),
                    'date': __import__('datetime').date,
                    'time': __import__('time'),
                    'json': __import__('json'),
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'len': len,
                }
                
                # Evaluate expression safely
                result = eval(field_mapping.mapping_expression, {"__builtins__": {}}, context)
                return result
                
            except Exception as e:
                _logger.error(f"[SYNC MANAGER] Error evaluating computed expression for field {field_mapping.name}: {str(e)}")
                if field_mapping.required:
                    raise
                return original_value
                
        elif mapping_type == 'relation':
            # Relation mapping - find related record by field value
            if not field_mapping.relation_model or not field_mapping.relation_field:
                _logger.warning(f"[SYNC MANAGER] Relation mapping requested but missing model or field for {field_mapping.name}")
                return original_value
                
            try:
                relation_model = self.env[field_mapping.relation_model]
                
                # Build domain
                domain = [(field_mapping.relation_field, '=', original_value)]
                
                # Add additional domain if specified
                if field_mapping.relation_domain:
                    try:
                        additional_domain = __import__('json').loads(field_mapping.relation_domain)
                        if isinstance(additional_domain, list):
                            domain.extend(additional_domain)
                    except __import__('json').JSONDecodeError:
                        _logger.warning(f"[SYNC MANAGER] Invalid relation domain JSON for field {field_mapping.name}")
                
                # Search for related record
                related_records = relation_model.search(domain, limit=1)
                if related_records:
                    return related_records.id
                else:
                    _logger.warning(f"[SYNC MANAGER] No related record found in {field_mapping.relation_model} with {field_mapping.relation_field}={original_value}")
                    return None
                    
            except Exception as e:
                _logger.error(f"[SYNC MANAGER] Error in relation mapping for field {field_mapping.name}: {str(e)}")
                if field_mapping.required:
                    raise
                return original_value
        
        else:
            _logger.warning(f"[SYNC MANAGER] Unknown mapping type: {mapping_type}")
            return original_value
    
    def set_conflict_strategy(self):
        """Set the system parameter for conflict resolution strategy based on the selected value."""
        self.ensure_one()
        if self.conflict_resolution_strategy:
            self.env['ir.config_parameter'].sudo().set_param(
                'odoo_to_odoo_sync.default_conflict_strategy', self.conflict_resolution_strategy) 
