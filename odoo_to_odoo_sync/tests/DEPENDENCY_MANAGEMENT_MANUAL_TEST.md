# Manual Testing Guide: Dependency Management

## Overview
This guide provides step-by-step instructions for manually testing the dependency management feature in your Odoo-to-Odoo sync module.

## Prerequisites
- Your traefik-test environment is running (both Odoo instances)
- The odoo_to_odoo_sync module is installed and updated
- You have access to both Odoo instances via web browser

## Test 1: Basic Dependency Detection

### Steps:
1. **Access Odoo Instance 1**: Open http://localhost:8069
2. **Navigate to**: Odoo Sync → Configuration → Models
3. **Create Test Models**:
   - Click "Create" to add new sync models
   - Create these models in order:
     - **Model**: res.partner
     - **Model**: res.users (depends on res.partner via partner_id field)
     - **Model**: sale.order (depends on res.partner via partner_id field)
     - **Model**: sale.order.line (depends on sale.order via order_id field)

4. **Activate Models**: Ensure all models are active
5. **Update Dependencies**: 
   - Go to Odoo Sync → Configuration → Dependency Resolver
   - Click on the resolver record
   - Click "Update Model Dependencies"

### Expected Results:
- Navigate to Odoo Sync → Configuration → Dependencies
- You should see dependency records created automatically
- Check for relationships like:
  - res.users → res.partner (Many2one)
  - sale.order → res.partner (Many2one)
  - sale.order.line → sale.order (Many2one)

## Test 2: Circular Dependency Detection

### Steps:
1. **Create Circular Dependency**:
   - Create 3 test models with custom fields:
   - Model A: has Many2one to Model B
   - Model B: has Many2one to Model C
   - Model C: has Many2one to Model A

2. **Update Dependencies**: Use the dependency resolver

### Expected Results:
- Circular dependencies should be detected and logged
- Check Odoo Sync → Logs for circular dependency warnings
- Dependencies should still be created but marked as circular

## Test 3: Processing Order Validation

### Steps:
1. **Create Sync Queue Items**:
   - Create sync queue items for models with dependencies
   - Ensure items are created in "wrong" order (dependent models first)

2. **Process Queue**:
   - Go to Odoo Sync → Queue
   - Process the queue items

### Expected Results:
- Items should be processed in dependency order
- Check the sync logs to verify processing sequence
- Items with unmet dependencies should be retried later

## Test 4: Missing Dependency Handling

### Steps:
1. **Create Incomplete Setup**:
   - Create a sync model that depends on another model
   - Do NOT create the dependent model
   - Create a sync queue item for the incomplete model

2. **Process Queue**:
   - Attempt to process the queue item

### Expected Results:
- The item should be marked as failed due to missing dependency
- Retry count should increment
- Error message should mention missing dependency

## Test 5: Integration Test

### Steps:
1. **Full Setup**:
   - Set up sync between two Odoo instances
   - Configure models with dependencies
   - Create records in source instance

2. **Trigger Sync**:
   - Create/update records in dependent order
   - Check sync results

### Expected Results:
- Records sync in correct dependency order
- No foreign key constraint violations
- All records sync successfully

## Validation Checklist

### Model Dependencies:
- [ ] Dependencies are automatically detected
- [ ] Dependency records are created correctly
- [ ] Circular dependencies are detected and logged
- [ ] Processing order respects dependencies

### Error Handling:
- [ ] Missing dependencies are handled gracefully
- [ ] Retry mechanism works for missing dependencies
- [ ] Error messages are clear and helpful

### Performance:
- [ ] Dependency resolution completes quickly
- [ ] No performance degradation with many models
- [ ] Memory usage remains reasonable

## Debug Commands

### Check Dependencies:
```python
# In Odoo shell
env['odoo.sync.dependency'].search([]).read(['source_model_id', 'target_model_id', 'relation_type'])
```

### Check Processing Order:
```python
# In Odoo shell
env['odoo.sync.queue'].search([]).sorted('processing_order').read(['model_id', 'state'])
```

### Force Dependency Update:
```python
# In Odoo shell
resolver = env['odoo.sync.dependency.resolver'].search([])[0]
resolver.update_model_dependencies()
```

## Troubleshooting

### Common Issues:
1. **Models not appearing**: Check if models are active in sync configuration
2. **Dependencies not created**: Verify models have actual field relationships
3. **Circular dependencies**: Review model relationships for actual cycles

### Debug Logs:
- Check Odoo logs for dependency management messages
- Look for entries with "dependency" or "resolver" keywords
- Enable debug logging if needed: `--log-level=debug`

## Success Criteria

All tests pass when:
- Dependencies are correctly detected and recorded
- Processing order respects dependencies
- Circular dependencies are handled
- Missing dependencies are retried appropriately
- No foreign key violations occur during sync
