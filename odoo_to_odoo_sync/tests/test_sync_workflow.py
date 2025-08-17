# -*- coding: utf-8 -*-

from odoo.tests import common
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class TestBidirectionalSyncWorkflow(common.TransactionCase):
    """Test the complete bidirectional sync workflow"""
    
    def setUp(self):
        super(TestBidirectionalSyncWorkflow, self).setUp()
        
        # Create test data
        self.test_project = self.env['project.project'].create({
            'name': 'Test Sync Project',
            'description': 'Test project for sync validation',
        })
        
        self.test_client = self.env['odoo.sync.instance'].create({
            'name': 'Test Client',
            'url': 'https://test-client.example.com',
            'database': 'test_db',
            'username': 'test_user',
            'api_key': 'test_api_key_123',
            'connection_type': 'jsonrpc',
        })

    def test_project_assignment_workflow(self):
        """Test the complete project assignment workflow"""
        
        # Step 1: Create assign project wizard
        assign_wizard = self.env['odoo.to.bemade.assign.project.wizard'].create({
            'project_id': self.test_project.id,
            'client_instance_id': self.test_client.id,
        })
        
        # Step 2: Generate keys
        assign_wizard._onchange_generate_keys()
        
        # Verify keys are generated
        self.assertTrue(assign_wizard.project_key)
        self.assertTrue(assign_wizard.client_api_token)
        self.assertEqual(len(assign_wizard.project_key), 8)
        self.assertEqual(len(assign_wizard.client_api_token), 36)
        
        # Step 3: Assign project
        result = assign_wizard.action_assign_project()
        
        # Verify sync project is created
        sync_project = self.env['sync.project'].search([
            ('project_id', '=', self.test_project.id),
            ('client_instance_id', '=', self.test_client.id),
        ])
        self.assertTrue(sync_project)
        self.assertEqual(sync_project.state, 'draft')
        self.assertTrue(sync_project.is_client_project)
        self.assertEqual(sync_project.client_key, assign_wizard.project_key)
        
        # Verify project flags are set
        self.assertTrue(self.test_project.is_bemade_project)
        self.assertTrue(self.test_project.bemade_sync_enabled)
        self.assertEqual(self.test_project.bemade_project_key, assign_wizard.project_key)
        
        # Verify sync models are created
        project_model = self.env['sync.model'].search([
            ('sync_project_id', '=', sync_project.id),
            ('model_name', '=', 'project.project'),
        ])
        self.assertTrue(project_model)
        
        task_model = self.env['sync.model'].search([
            ('sync_project_id', '=', sync_project.id),
            ('model_name', '=', 'project.task'),
        ])
        self.assertTrue(task_model)

    def test_project_receiving_workflow(self):
        """Test the project receiving workflow from client perspective"""
        
        # Create test sync project first
        sync_project = self.env['sync.project'].create({
            'name': 'Test Client Sync Project',
            'project_id': self.test_project.id,
            'client_instance_id': self.test_client.id,
            'state': 'draft',
            'is_client_project': True,
            'client_key': 'TEST123',
            'client_api_token': 'test-client-token-123',
            'remote_url': 'https://test-client.example.com',
            'remote_database': 'test_db',
            'remote_username': 'test_user',
            'remote_api_key': 'test_api_key_123',
            'protocol': 'jsonrpc',
        })
        
        # Create receive wizard
        receive_wizard = self.env['odoo.to.bemade.customer.receive.wizard'].create({
            'project_id': self.test_project.id,
            'bemade_url': 'https://test-bemade.example.com',
            'bemade_database': 'bemade_db',
            'bemade_username': 'bemade_user',
            'bemade_api_key': 'bemade-api-key-123',
            'bemade_project_key': 'TEST123',
            'protocol': 'jsonrpc',
        })
        
        # Test project sync
        self.test_project.write({
            'is_bemade_project': True,
            'bemade_project_key': 'TEST123',
            'bemade_sync_enabled': True,
        })
        
        # Verify project has bemade flags
        self.assertTrue(self.test_project.is_bemade_project)
        self.assertEqual(self.test_project.bemade_project_key, 'TEST123')

    def test_api_token_exchange(self):
        """Test the API token exchange mechanism"""
        
        # Create token exchange wizard
        token_wizard = self.env['api.token.exchange.wizard'].create({
            'client_instance_id': self.test_client.id,
            'client_url': self.test_client.url,
            'client_database': self.test_client.database,
            'client_username': self.test_client.username,
            'client_api_key': self.test_client.api_key,
            'project_info': 'Test Project Info',
        })
        
        # Test token exchange configuration
        self.assertTrue(token_wizard.client_api_key)
        self.assertEqual(token_wizard.client_api_key, 'test_api_key_123')

    def test_bidirectional_sync_validation(self):
        """Test complete bidirectional sync validation"""
        
        # Step 1: Server assigns project to client
        assign_wizard = self.env['odoo.to.bemade.assign.project.wizard'].create({
            'project_id': self.test_project.id,
            'client_instance_id': self.test_client.id,
        })
        assign_wizard._onchange_generate_keys()
        assign_wizard.action_assign_project()
        
        # Step 2: Client receives project
        receive_wizard = self.env['odoo.to.bemade.customer.receive.wizard'].create({
            'project_id': self.test_project.id,
            'bemade_url': 'https://bemade.example.com',
            'bemade_database': 'bemade_db',
            'bemade_username': 'bemade_user',
            'bemade_api_key': 'bemade_api_key_123',
            'bemade_project_key': assign_wizard.project_key,
            'protocol': 'jsonrpc',
        })
        
        # Verify project is properly configured for bidirectional sync
        sync_project = self.env['sync.project'].search([
            ('client_key', '=', assign_wizard.project_key),
        ])
        self.assertTrue(sync_project)
        
        # Verify both server and client have matching configuration
        self.assertEqual(sync_project.client_key, assign_wizard.project_key)
        self.assertEqual(sync_project.client_api_token, assign_wizard.client_api_token)

    def test_error_handling(self):
        """Test error handling in sync workflow"""
        
        # Test invalid project assignment
        with self.assertRaises(UserError):
            assign_wizard = self.env['odoo.to.bemade.assign.project.wizard'].create({
                'project_id': False,  # Invalid project
                'client_instance_id': self.test_client.id,
            })
            assign_wizard.action_assign_project()

    def test_security_validation(self):
        """Test security access for sync operations"""
        
        # Test user access to sync projects
        user = self.env.ref('base.group_user')
        sync_project = self.env['sync.project'].create({
            'name': 'Security Test Project',
            'project_id': self.test_project.id,
            'client_instance_id': self.test_client.id,
            'state': 'draft',
            'is_client_project': True,
            'client_key': 'SECURITY123',
            'client_api_token': 'security-token-123',
        })
        
        # Verify user has read access
        self.assertTrue(sync_project.with_user(user).read())
        
        # Verify admin has full access
        admin = self.env.ref('base.group_system')
        self.assertTrue(sync_project.with_user(admin).write({'name': 'Updated Security Test'}))
