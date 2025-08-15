# -*- coding: utf-8 -*-
"""
Dependency Management for Odoo-to-Odoo Sync Module

This module provides automatic dependency handling between models during synchronization.
It analyzes model relationships and ensures proper processing order to prevent
synchronization failures due to missing related records.
"""

import logging
from collections import defaultdict, deque
from odoo import api, fields, models, exceptions
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OdooSyncDependency(models.Model):
    """Model to track and manage dependencies between synchronized models."""
    
    _name = 'odoo.sync.dependency'
    _description = 'Synchronization Dependency Management'
    _order = 'sequence, id'
    
    model_sync_id = fields.Many2one(
        comodel_name='odoo.sync.model',
        string='Synchronized Model',
        required=True,
        ondelete='cascade'
    )
    
    depends_on_model_id = fields.Many2one(
        comodel_name='odoo.sync.model',
        string='Depends On Model',
        required=True,
        ondelete='cascade'
    )
    
    relation_type = fields.Selection([
        ('many2one', 'Many2one'),
        ('one2many', 'One2many'),
        ('many2many', 'Many2many'),
        ('parent', 'Parent/Child'),
        ('inheritance', 'Inheritance')
    ], string='Relation Type', required=True)
    
    field_name = fields.Char(
        string='Field Name',
        help='Name of the field that creates this dependency'
    )
    
    sequence = fields.Integer(
        string='Processing Order',
        default=10,
        help='Order in which dependencies should be processed'
    )
    
    is_circular = fields.Boolean(
        string='Circular Dependency',
        default=False,
        help='Indicates if this dependency creates a circular reference'
    )
    
    auto_detected = fields.Boolean(
        string='Auto Detected',
        default=True,
        help='Whether this dependency was automatically detected'
    )
    
    _sql_constraints = [
        ('unique_dependency', 
         'unique(model_sync_id, depends_on_model_id, field_name)',
         'A dependency can only be defined once per field')
    ]


class OdooSyncDependencyResolver(models.Model):
    """Service model for resolving dependencies during synchronization."""
    
    _name = 'odoo.sync.dependency.resolver'
    _description = 'Dependency Resolver'
    
    @api.model
    def analyze_model_dependencies(self, model_sync_ids):
        """
        Analyze dependencies for a set of synchronized models.
        
        Args:
            model_sync_ids: List of odoo.sync.model IDs
            
        Returns:
            dict: Dependency graph and processing order
        """
        models = self.env['odoo.sync.model'].browse(model_sync_ids)
        
        # Build dependency graph
        graph = defaultdict(set)
        model_map = {}
        
        for model_sync in models:
            model_map[model_sync.model_id.model] = model_sync
            
        # Analyze relationships
        for model_sync in models:
            self._analyze_model_relationships(model_sync, model_map, graph)
        
        # Detect circular dependencies
        cycles = self._detect_cycles(graph)
        
        # Generate processing order using topological sort
        processing_order = self._topological_sort(graph)
        
        return {
            'graph': dict(graph),
            'cycles': cycles,
            'processing_order': processing_order,
            'model_map': model_map
        }
    
    def _analyze_model_relationships(self, model_sync, model_map, graph):
        """Analyze relationships for a single model."""
        model_name = model_sync.model_id.model
        
        # Get the actual Odoo model
        try:
            model = self.env[model_name]
        except KeyError:
            _logger.warning(f"Model {model_name} not found, skipping dependency analysis")
            return
        
        # Analyze fields for dependencies
        for field_name, field in model._fields.items():
            if field.type in ['many2one', 'one2many', 'many2many']:
                related_model = field.comodel_name
                
                if related_model in model_map and related_model != model_name:
                    # Create dependency record
                    dependency_vals = {
                        'model_sync_id': model_sync.id,
                        'depends_on_model_id': model_map[related_model].id,
                        'relation_type': field.type,
                        'field_name': field_name,
                        'auto_detected': True
                    }
                    
                    # Check if dependency already exists
                    existing = self.env['odoo.sync.dependency'].search([
                        ('model_sync_id', '=', model_sync.id),
                        ('depends_on_model_id', '=', model_map[related_model].id),
                        ('field_name', '=', field_name)
                    ])
                    
                    if not existing:
                        self.env['odoo.sync.dependency'].create(dependency_vals)
                    
                    # Add to graph
                    graph[model_name].add(related_model)
    
    def _detect_cycles(self, graph):
        """Detect circular dependencies in the graph."""
        cycles = []
        visited = set()
        path = set()
        
        def dfs(node, current_path=None):
            if current_path is None:
                current_path = []
                
            if node in current_path:
                cycle_start = current_path.index(node)
                cycle = current_path[cycle_start:] + [node]
                cycles.append(cycle)
                return
                
            if node in visited:
                return
                
            visited.add(node)
            current_path.append(node)
            
            for neighbor in graph.get(node, set()):
                dfs(neighbor, current_path.copy())
                
            current_path.pop()
        
        for node in graph:
            if node not in visited:
                dfs(node)
        
        return cycles
    
    def _topological_sort(self, graph):
        """Generate processing order using topological sort."""
        # Kahn's algorithm for topological sorting
        in_degree = defaultdict(int)
        for node in graph:
            in_degree[node] = 0
        
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1
        
        queue = deque([node for node in in_degree if in_degree[node] == 0])
        order = []
        
        while queue:
            node = queue.popleft()
            order.append(node)
            
            for neighbor in graph.get(node, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Handle cycles - add remaining nodes
        remaining = set(graph.keys()) - set(order)
        order.extend(sorted(remaining))
        
        return order
    
    @api.model
    def get_processing_order(self, model_sync_ids):
        """Get the processing order for synchronized models."""
        analysis = self.analyze_model_dependencies(model_sync_ids)
        
        # Convert model names back to sync model IDs
        model_map = analysis['model_map']
        processing_order = []
        
        for model_name in analysis['processing_order']:
            if model_name in model_map:
                processing_order.append(model_map[model_name].id)
        
        return processing_order
    
    @api.model
    def resolve_missing_dependencies(self, queue_item):
        """
        Check if a queue item has missing dependencies and handle them.
        
        Args:
            queue_item: odoo.sync.queue record
            
        Returns:
            bool: True if dependencies are resolved, False otherwise
        """
        model_name = queue_item.model_id.model
        record_data = queue_item.get_record_data()
        
        missing_deps = []
        
        # Check for missing related records
        for field_name, field_value in record_data.items():
            if isinstance(field_value, (list, tuple)) and len(field_value) == 2:
                # This is likely a relation field
                related_model = self.env[model_name]._fields[field_name].comodel_name
                
                # Check if the related record exists on the destination
                dest_instance = queue_item.other_odoo_id
                try:
                    dest_instance.execute_kw(
                        related_model, 'search_read',
                        [[('id', '=', field_value[0])]],
                        {'fields': ['id'], 'limit': 1}
                    )
                except Exception:
                    # Record doesn't exist, add to missing dependencies
                    missing_deps.append({
                        'model': related_model,
                        'id': field_value[0],
                        'field': field_name
                    })
        
        if missing_deps:
            # Queue item has missing dependencies
            _logger.info(f"Queue item {queue_item.id} has missing dependencies: {missing_deps}")
            
            # Update retry count and set next retry time
            queue_item.write({
                'retry_count': queue_item.retry_count + 1,
                'next_retry': fields.Datetime.now(),
                'error_message': f"Missing dependencies: {missing_deps}"
            })
            
            return False
        
        return True
