from odoo.tests import TransactionCase, tagged, Form


@tagged('post_install', '-at_install')
class TestMrpMtsElseMto(TransactionCase):
    """Test parent-child MO relationships with mts_else_mto rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get warehouse and locations
        cls.warehouse = cls.env.ref('stock.warehouse0')
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.production_location = cls.warehouse.manu_type_id.default_location_dest_id
        
        # Create products for multi-level BOM
        # Top level product
        cls.product_final = cls.env['product.product'].create({
            'name': 'Final Product',
            'type': 'consu',
            'is_storable': True,
            'route_ids': [(4, cls.env.ref('mrp.route_warehouse0_manufacture').id)],
        })
        
        # Sub-assembly (component of final, has its own BOM)
        cls.product_subassembly = cls.env['product.product'].create({
            'name': 'Sub-Assembly',
            'type': 'consu',
            'is_storable': True,
            'route_ids': [(4, cls.env.ref('mrp.route_warehouse0_manufacture').id)],
        })
        
        # Raw material (component of sub-assembly)
        cls.product_raw = cls.env['product.product'].create({
            'name': 'Raw Material',
            'type': 'consu',
            'is_storable': True,
        })
        
        # Create BOM for sub-assembly
        cls.bom_subassembly = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.product_subassembly.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {
                    'product_id': cls.product_raw.id,
                    'product_qty': 2.0,
                }),
            ],
        })
        
        # Create BOM for final product (uses sub-assembly)
        cls.bom_final = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.product_final.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {
                    'product_id': cls.product_subassembly.id,
                    'product_qty': 1.0,
                }),
            ],
        })
        
        # Get the manufacture route and its rule
        cls.manufacture_route = cls.env.ref('mrp.route_warehouse0_manufacture')
        cls.manufacture_rule = cls.env['stock.rule'].search([
            ('route_id', '=', cls.manufacture_route.id),
            ('action', '=', 'manufacture'),
        ], limit=1)

    def test_01_mto_rule_creates_linked_child_mo(self):
        """Test that make_to_order rules create properly linked child MOs."""
        # Set rule to make_to_order
        self.manufacture_rule.procure_method = 'make_to_order'
        
        # Create and confirm parent MO
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.product_final
        mo_form.product_qty = 1.0
        parent_mo = mo_form.save()
        parent_mo.action_confirm()
        
        # Check that child MO was created and linked
        self.assertEqual(parent_mo.mrp_production_child_count, 1,
                        "Parent MO should have 1 child with make_to_order rule")
        
        children = parent_mo._get_children()
        self.assertEqual(len(children), 1, "Should find 1 child MO")
        self.assertEqual(children.product_id, self.product_subassembly,
                        "Child MO should be for sub-assembly")
        
        # Verify the link through move_dest_ids
        raw_move = parent_mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.product_subassembly
        )
        self.assertTrue(raw_move, "Parent should have raw move for sub-assembly")
        self.assertEqual(raw_move.created_production_id, children,
                        "Raw move should link to child MO via created_production_id")

    def test_02_mts_else_mto_rule_creates_linked_child_mo(self):
        """Test that mts_else_mto rules create properly linked child MOs (the fix)."""
        # Set rule to mts_else_mto
        self.manufacture_rule.procure_method = 'mts_else_mto'
        
        # Create and confirm parent MO
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.product_final
        mo_form.product_qty = 1.0
        parent_mo = mo_form.save()
        parent_mo.action_confirm()
        
        # Check that child MO was created and linked
        self.assertEqual(parent_mo.mrp_production_child_count, 1,
                        "Parent MO should have 1 child with mts_else_mto rule")
        
        children = parent_mo._get_children()
        self.assertEqual(len(children), 1, "Should find 1 child MO")
        self.assertEqual(children.product_id, self.product_subassembly,
                        "Child MO should be for sub-assembly")
        
        # Verify the link through move_dest_ids
        raw_move = parent_mo.move_raw_ids.filtered(
            lambda m: m.product_id == self.product_subassembly
        )
        self.assertTrue(raw_move, "Parent should have raw move for sub-assembly")
        self.assertEqual(raw_move.created_production_id, children,
                        "Raw move should link to child MO via created_production_id")

    def test_03_mts_else_mto_quantity_propagation(self):
        """Test that quantity changes propagate from parent to child with mts_else_mto."""
        # Set rule to mts_else_mto
        self.manufacture_rule.procure_method = 'mts_else_mto'
        
        # Create and confirm parent MO
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.product_final
        mo_form.product_qty = 1.0
        parent_mo = mo_form.save()
        parent_mo.action_confirm()
        
        # Get child MO
        child_mo = parent_mo._get_children()
        self.assertEqual(len(child_mo), 1)
        initial_child_qty = child_mo.product_qty
        
        # Change parent quantity
        wizard = self.env['change.production.qty'].create({
            'mo_id': parent_mo.id,
            'product_qty': 2.0,
        })
        wizard.change_prod_qty()
        
        # Verify child quantity updated
        child_mo.invalidate_recordset()
        self.assertEqual(child_mo.product_qty, initial_child_qty * 2,
                        "Child MO quantity should double when parent doubles")

    def test_04_mts_else_mto_parent_navigation(self):
        """Test that we can navigate from child to parent with mts_else_mto."""
        # Set rule to mts_else_mto
        self.manufacture_rule.procure_method = 'mts_else_mto'
        
        # Create and confirm parent MO
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.product_final
        mo_form.product_qty = 1.0
        parent_mo = mo_form.save()
        parent_mo.action_confirm()
        
        # Get child MO
        child_mo = parent_mo._get_children()
        self.assertEqual(len(child_mo), 1)
        
        # Check parent navigation from child
        self.assertEqual(child_mo.mrp_production_source_count, 1,
                        "Child should have 1 parent/source MO")
        
        sources = child_mo._get_sources()
        self.assertEqual(len(sources), 1, "Should find 1 source MO")
        self.assertEqual(sources, parent_mo, "Source should be the parent MO")

    def test_05_prepare_procurement_values_with_mts_else_mto(self):
        """Test that _prepare_procurement_values includes move_dest_ids for mts_else_mto."""
        # Set rule to mts_else_mto
        self.manufacture_rule.procure_method = 'mts_else_mto'
        
        # Create a stock move that would trigger manufacturing
        move = self.env['stock.move'].create({
            'name': 'Test Move',
            'product_id': self.product_subassembly.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_subassembly.uom_id.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.production_location.id,
            'procure_method': 'make_to_stock',  # This is what _adjust_procure_method sets
            'rule_id': self.manufacture_rule.id,
        })
        
        # Call _prepare_procurement_values
        values = move._prepare_procurement_values()
        
        # Verify move_dest_ids is included
        self.assertEqual(values.get('move_dest_ids'), move,
                        "move_dest_ids should be included for mts_else_mto rule")

    def test_06_prepare_procurement_values_with_mto(self):
        """Test that _prepare_procurement_values still works correctly for make_to_order."""
        # Set rule to make_to_order
        self.manufacture_rule.procure_method = 'make_to_order'
        
        # Create a stock move
        move = self.env['stock.move'].create({
            'name': 'Test Move',
            'product_id': self.product_subassembly.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_subassembly.uom_id.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.production_location.id,
            'procure_method': 'make_to_order',
            'rule_id': self.manufacture_rule.id,
        })
        
        # Call _prepare_procurement_values
        values = move._prepare_procurement_values()
        
        # Verify move_dest_ids is included (standard behavior)
        self.assertEqual(values.get('move_dest_ids'), move,
                        "move_dest_ids should be included for make_to_order")

    def test_07_prepare_procurement_values_with_mts(self):
        """Test that _prepare_procurement_values doesn't include move_dest_ids for pure make_to_stock."""
        # Set rule to make_to_stock
        self.manufacture_rule.procure_method = 'make_to_stock'
        
        # Create a stock move
        move = self.env['stock.move'].create({
            'name': 'Test Move',
            'product_id': self.product_subassembly.id,
            'product_uom_qty': 1.0,
            'product_uom': self.product_subassembly.uom_id.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.production_location.id,
            'procure_method': 'make_to_stock',
            'rule_id': self.manufacture_rule.id,
        })
        
        # Call _prepare_procurement_values
        values = move._prepare_procurement_values()
        
        # Verify move_dest_ids is NOT included (correct behavior for MTS)
        self.assertFalse(values.get('move_dest_ids'),
                        "move_dest_ids should NOT be included for pure make_to_stock")

    def test_08_three_level_bom_with_mts_else_mto(self):
        """Test three-level BOM with mts_else_mto rules."""
        # Set rule to mts_else_mto
        self.manufacture_rule.procure_method = 'mts_else_mto'
        
        # Create another level: component for raw material
        product_base = self.env['product.product'].create({
            'name': 'Base Component',
            'type': 'consu',
            'is_storable': True,
            'route_ids': [(4, self.manufacture_route.id)],
        })
        
        # Update raw material to have a BOM
        bom_raw = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_raw.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {
                    'product_id': product_base.id,
                    'product_qty': 1.0,
                }),
            ],
        })
        
        # Create and confirm top-level MO
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.product_final
        mo_form.product_qty = 1.0
        top_mo = mo_form.save()
        top_mo.action_confirm()
        
        # Check first level children
        level1_children = top_mo._get_children()
        self.assertEqual(len(level1_children), 1, "Should have 1 first-level child")
        self.assertEqual(level1_children.product_id, self.product_subassembly)
        
        # Confirm first level child to trigger second level
        level1_children.action_confirm()
        
        # Check second level children
        level2_children = level1_children._get_children()
        self.assertEqual(len(level2_children), 1, "Should have 1 second-level child")
        self.assertEqual(level2_children.product_id, self.product_raw)
        
        # Verify all links are correct
        self.assertEqual(level1_children.mrp_production_source_count, 1)
        self.assertEqual(level2_children.mrp_production_source_count, 1)
        
        # Verify we can navigate the full chain
        self.assertIn(top_mo, level1_children._get_sources())
        self.assertIn(level1_children, level2_children._get_sources())
