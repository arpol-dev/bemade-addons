# Copyright 2025 Codeium
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html)

"""Synchronization Queue Management.

This module implements the queue system for managing synchronization operations
between Odoo instances. It handles the scheduling, retry logic, and status
tracking of synchronization tasks.
"""

import json
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class OdooSyncQueue(models.Model):
    _name = 'odoo.sync.queue'
    _description = 'Synchronization Queue'
    _order = 'priority desc, retry_count, create_date'

    name = fields.Char(
        string='Name', 
        compute='_compute_name', 
        store=True
    )

    model_id = fields.Many2one(
        comodel_name='odoo.sync.model',
        string='Model',
        required=True
    )

    record_id = fields.Integer(
        string='Record ID', 
        required=True
    )

    operation = fields.Selection(
        selection=[
            ('create', 'Create'),
            ('write', 'Update'),
            ('unlink', 'Delete')
        ],
        required=True
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('done', 'Done'),
            ('error', 'Error'),
            ('cancelled', 'Cancelled')
        ],
        default='draft', 
        required=True
    )

    priority = fields.Integer(
        string='Priority', 
        default=1
    )

    retry_count = fields.Integer(
        string='Retry Count', 
        default=0
    )

    max_retries = fields.Integer(
        string='Max Retries', 
        default=3
    )

    next_retry = fields.Datetime(
        string='Next Retry'
    )

    data = fields.Text(
        string='Data', 
        help='JSON data to synchronize'
    )

    error_message = fields.Text(
        string='Error Message'
    )

    log_ids = fields.One2many(
        comodel_name='odoo.sync.log', 
        inverse_name='queue_id', 
        string='Logs'
    )

    @api.depends('model_id', 'record_id', 'operation')
    def _compute_name(self):
        """Compute the display name of the queue entry.
        
        The name is generated using the format: 'operation - model_name#record_id'
        e.g., 'create - res.partner#42'
        
        Triggered by changes to: model_id, record_id, or operation fields.
        """
        for record in self:
            record.name = f'{record.operation} - {record.model_id.name}#{record.record_id}'

    def action_reset(self):
        """Reset a failed queue entry to pending state.
        
        This method:
        - Changes state back to 'pending'
        - Resets retry count to 0
        - Clears error message and next retry time
        
        Returns:
            dict: Result of the write operation
        """
        return self.write({
            'state': 'pending',
            'retry_count': 0,
            'error_message': False,
            'next_retry': False
        })

    def action_cancel(self):
        """Cancel the queue entry.
        
        Changes the state of the queue entry to 'cancelled',
        preventing further processing attempts.
        
        Returns:
            dict: Result of the write operation
        """
        return self.write({'state': 'cancelled'})

    @api.model
    def _process_sync_queue(self):
        """Process pending synchronization queue entries.
        
        This method is called by the cron job to process pending queue entries.
        It will:
        1. Find pending entries that are ready for processing
        2. Dequeue each entry and pass it to the sync manager for processing
        3. Update the entry status based on the processing result
        
        Returns:
            bool: True if processing completed successfully
        """
        # Find pending entries ready for processing
        domain = [
            ('state', '=', 'pending'),
            '|',
            ('next_retry', '=', False),
            ('next_retry', '<=', fields.Datetime.now())
        ]
        entries = self.search(domain, order='priority desc, retry_count, create_date')
        
        for entry in entries:
            # Dequeue the item and process it
            sync_manager = self.env['odoo.sync.manager']
            sync_manager._process_dequeued_item(self.dequeue(entry.id))
            
        return True
    
    @api.model
    def dequeue(self, queue_id):
        """Dequeue a specific queue item for processing.
        
        This method explicitly implements the "Dequeue" step in the synchronization
        sequence diagram. It marks the queue item as processing and returns it
        for further processing by the sync manager.
        
        Args:
            queue_id: ID of the queue item to dequeue
            
        Returns:
            odoo.sync.queue: The dequeued queue item record or False if not found
        """
        queue_item = self.browse(queue_id)
        if not queue_item.exists():
            _logger.error(f"[SYNC QUEUE] Cannot dequeue item {queue_id}: record not found")
            return False
            
        _logger.debug(f"[SYNC QUEUE] Dequeuing item {queue_id}")
        queue_item.write({'state': 'processing'})
        return queue_item
        
    def mark_success(self):
        """Mark this queue item as successfully processed.
        
        This method implements the 'Mark Success' step in the synchronization sequence diagram.
        """
        _logger.debug(f"[SYNC QUEUE] Marking item {self.id} as done")
        self.write({'state': 'done'})
        
        # Create success log
        self.env['odoo.sync.log'].create({
            'queue_id': self.id,
            'state': 'success',
            'message': f'Synchronisation réussie'
        })
        
    def increment_retry(self, error_message):
        """Increment the retry count for this queue item.
        
        This method implements the 'Increment Retry' step in the synchronization sequence diagram.
        
        Args:
            error_message: The error message to log
        """
        _logger.debug(f"[SYNC QUEUE] Incrementing retry count for item {self.id}")
        
        vals = {
            'state': 'error',
            'error_message': error_message,
            'retry_count': self.retry_count + 1
        }
        
        if self.retry_count + 1 < self.max_retries:
            # Exponential backoff
            delay = 2 ** (self.retry_count + 1)
            vals['next_retry'] = fields.Datetime.now() + timedelta(minutes=delay)
        
        self.write(vals)
        
        # Create error log
        self.env['odoo.sync.log'].create({
            'queue_id': self.id,
            'state': 'error',
            'message': error_message,
            'details': error_message
        })
        
        return True
