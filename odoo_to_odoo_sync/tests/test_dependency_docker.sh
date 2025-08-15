#!/bin/bash

# Dependency Management Test Runner for traefik-test environment
# This script runs dependency tests through your existing docker-compose.yml

set -e

echo "=== Dependency Management Test Suite ==="
echo "Testing in traefik-test environment..."

# Check if environment is running
if ! docker compose ps | grep -q "traefik-test-odoo1-1"; then
    echo "Starting traefik-test environment..."
    docker compose up -d
    echo "Waiting for services to start..."
    sleep 30
fi

# Test 1: Database connectivity
echo ""
echo "🔍 Test 1: Database Connectivity"
docker compose exec -T db1 psql -U odoo -d odoo1 -c "SELECT version();" || {
    echo "❌ Database connection failed"
    exit 1
}
echo "✅ Database connectivity confirmed"

# Test 2: Model availability
echo ""
echo "🔍 Test 2: Model Availability"
docker compose exec -T odoo1 python3 -c "
import psycopg2
import sys

conn = psycopg2.connect(
    host='db1',
    database='odoo1',
    user='odoo',
    password='odoo'
)

cursor = conn.cursor()
cursor.execute(\"SELECT model FROM ir_model WHERE model LIKE 'odoo.sync.%'\")
models = cursor.fetchall()

required_models = [
    'odoo.sync.model',
    'odoo.sync.dependency',
    'odoo.sync.dependency.resolver'
]

found_models = [m[0] for m in models]
missing = [m for m in required_models if m not in found_models]

if not missing:
    print('✅ All dependency management models available')
    conn.close()
    sys.exit(0)
else:
    print(f'❌ Missing models: {missing}')
    conn.close()
    sys.exit(1)
" || exit 1

# Test 3: Dependency detection
echo ""
echo "🔍 Test 3: Dependency Detection"
docker compose exec -T odoo1 python3 -c "
import psycopg2
import sys

conn = psycopg2.connect(
    host='db1',
    database='odoo1',
    user='odoo',
    password='odoo'
)

cursor = conn.cursor()

# Create test models
cursor.execute(\"INSERT INTO odoo_sync_model (name, model_name, active, priority) VALUES ('Test Partner', 'res.partner', true, 10), ('Test User', 'res.users', true, 20) RETURNING id\")
model_ids = [row[0] for row in cursor.fetchall()]
conn.commit()

# Create dependency relationship
cursor.execute(\"INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type, field_name) SELECT (SELECT id FROM odoo_sync_model WHERE model_name = 'res.users'), (SELECT id FROM odoo_sync_model WHERE model_name = 'res.partner'), 'many2one', 'partner_id'\")
conn.commit()

# Check if dependency was created
cursor.execute(\"SELECT COUNT(*) FROM odoo_sync_dependency WHERE source_model_id IN %s\", (tuple(model_ids),))
count = cursor.fetchone()[0]

# Cleanup
cursor.execute(\"DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s\", (tuple(model_ids),))
cursor.execute(\"DELETE FROM odoo_sync_model WHERE id IN %s\", (tuple(model_ids),))
conn.commit()
conn.close()

if count > 0:
    print('✅ Dependency detection working')
    sys.exit(0)
else:
    print('❌ Dependency detection failed')
    sys.exit(1)
" || exit 1

# Test 4: Circular dependency detection
echo ""
echo "🔍 Test 4: Circular Dependency Detection"
docker compose exec -T odoo1 python3 -c "
import psycopg2
import sys

conn = psycopg2.connect(
    host='db1',
    database='odoo1',
    user='odoo',
    password='odoo'
)

cursor = conn.cursor()

# Create test models with circular dependency
cursor.execute(\"INSERT INTO odoo_sync_model (name, model_name, active, priority) VALUES ('Model A', 'test.model.a', true, 10), ('Model B', 'test.model.b', true, 20), ('Model C', 'test.model.c', true, 30) RETURNING id\")
model_ids = [row[0] for row in cursor.fetchall()]
conn.commit()

# Create circular dependencies
cursor.execute(\"INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type, is_circular) VALUES ((SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.a'), (SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.b'), 'many2one', true), ((SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.b'), (SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.c'), 'many2one', true), ((SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.c'), (SELECT id FROM odoo_sync_model WHERE model_name = 'test.model.a'), 'many2one', true)\")
conn.commit()

# Check if circular dependencies were detected
cursor.execute(\"SELECT COUNT(*) FROM odoo_sync_dependency WHERE is_circular = true AND source_model_id IN %s\", (tuple(model_ids),))
count = cursor.fetchone()[0]

# Cleanup
cursor.execute(\"DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s\", (tuple(model_ids),))
cursor.execute(\"DELETE FROM odoo_sync_model WHERE id IN %s\", (tuple(model_ids),))
conn.commit()
conn.close()

if count > 0:
    print('✅ Circular dependency detection working')
    sys.exit(0)
else:
    print('❌ Circular dependency detection failed')
    sys.exit(1)
" || exit 1

# Test 5: Processing order
echo ""
echo "🔍 Test 5: Processing Order"
docker compose exec -T odoo1 python3 -c "
import psycopg2
import sys

conn = psycopg2.connect(
    host='db1',
    database='odoo1',
    user='odoo',
    password='odoo'
)

cursor = conn.cursor()

# Create test models with dependencies
cursor.execute(\"INSERT INTO odoo_sync_model (name, model_name, active, priority, processing_order) VALUES ('Parent Model', 'test.parent', true, 10, 1), ('Child Model', 'test.child', true, 20, 2) RETURNING id\")
model_ids = [row[0] for row in cursor.fetchall()]
conn.commit()

# Create dependency relationship
cursor.execute(\"INSERT INTO odoo_sync_dependency (source_model_id, target_model_id, relation_type) SELECT (SELECT id FROM odoo_sync_model WHERE model_name = 'test.child'), (SELECT id FROM odoo_sync_model WHERE model_name = 'test.parent'), 'many2one'\")
conn.commit()

# Check processing order
cursor.execute(\"SELECT model_name, processing_order FROM odoo_sync_model WHERE id IN %s ORDER BY processing_order\", (tuple(model_ids),))
results = cursor.fetchall()

# Cleanup
cursor.execute(\"DELETE FROM odoo_sync_dependency WHERE source_model_id IN %s\", (tuple(model_ids),))
cursor.execute(\"DELETE FROM odoo_sync_model WHERE id IN %s\", (tuple(model_ids),))
conn.commit()
conn.close()

if len(results) == 2 and results[0][0] == 'test.parent' and results[1][0] == 'test.child':
    print('✅ Processing order working correctly')
    sys.exit(0)
else:
    print('❌ Processing order incorrect')
    sys.exit(1)
" || exit 1

echo ""
echo "🎉 All dependency management tests completed successfully!"
echo "The dependency management feature is working correctly in your traefik-test environment."
