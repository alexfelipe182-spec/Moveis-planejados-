-- Multi-Marcenarias: PostgreSQL, banco/schema NOVO e vazio somente.
-- Gerado pelas migracoes Alembic; nao recupera registros de um banco perdido.
-- Para banco existente: backup primeiro, depois alembic upgrade head.
BEGIN;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
    ) THEN
        RAISE EXCEPTION 'Schema nao vazio: use backup e alembic upgrade head';
    END IF;
END $$;


CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 001_initial

CREATE TABLE users (
    id SERIAL NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    is_admin BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE categories (
    id SERIAL NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    description VARCHAR(500), 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE TABLE customers (
    id SERIAL NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    email VARCHAR(255), 
    phone VARCHAR(30), 
    address VARCHAR(500), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE products (
    id SERIAL NOT NULL, 
    category_id INTEGER NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description VARCHAR(1000), 
    price NUMERIC(12, 2) NOT NULL, 
    image_url VARCHAR(500), 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE TABLE quotes (
    id SERIAL NOT NULL, 
    customer_id INTEGER NOT NULL, 
    description TEXT NOT NULL, 
    total NUMERIC(12, 2) NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(customer_id) REFERENCES customers (id)
);

INSERT INTO alembic_version (version_num) VALUES ('001_initial') RETURNING alembic_version.version_num;

-- Running upgrade 001_initial -> 002_refresh_tokens

CREATE TABLE refresh_tokens (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    token_jti VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    revoked BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (token_jti)
);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);

CREATE UNIQUE INDEX ix_refresh_tokens_token_jti ON refresh_tokens (token_jti);

UPDATE alembic_version SET version_num='002_refresh_tokens' WHERE alembic_version.version_num = '001_initial';

-- Running upgrade 002_refresh_tokens -> 003_projects_history_pw_reset

ALTER TABLE quotes ADD COLUMN measurements VARCHAR(2000);

ALTER TABLE quotes ADD COLUMN materials VARCHAR(2000);

ALTER TABLE quotes ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE quotes SET updated_at = created_at WHERE updated_at IS NULL;

CREATE TABLE projects (
    id SERIAL NOT NULL, 
    customer_id INTEGER NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description TEXT, 
    measurements VARCHAR(2000), 
    materials VARCHAR(2000), 
    status VARCHAR(30) DEFAULT 'planning' NOT NULL, 
    project_date DATE, 
    photos JSON DEFAULT '[]' NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE
);

CREATE INDEX ix_projects_customer_id ON projects (customer_id);

CREATE INDEX ix_projects_name ON projects (name);

CREATE INDEX ix_projects_status ON projects (status);

CREATE TABLE activities (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    action VARCHAR(40) NOT NULL, 
    entity VARCHAR(60) NOT NULL, 
    entity_id INTEGER, 
    description VARCHAR(500) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_activities_user_id ON activities (user_id);

CREATE INDEX ix_activities_action ON activities (action);

CREATE INDEX ix_activities_entity ON activities (entity);

CREATE INDEX ix_activities_entity_id ON activities (entity_id);

CREATE INDEX ix_activities_created_at ON activities (created_at);

CREATE TABLE password_reset_tokens (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (token_hash)
);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);

UPDATE alembic_version SET version_num='003_projects_history_pw_reset' WHERE alembic_version.version_num = '002_refresh_tokens';

-- Running upgrade 003_projects_history_pw_reset -> 004_smart_quote_pricing

ALTER TABLE quotes ADD COLUMN material_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL;

ALTER TABLE quotes ADD COLUMN hardware_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL;

ALTER TABLE quotes ADD COLUMN labor_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL;

ALTER TABLE quotes ADD COLUMN finishing_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL;

ALTER TABLE quotes ADD COLUMN profit_margin NUMERIC(5, 2) DEFAULT '30' NOT NULL;

ALTER TABLE quotes ADD COLUMN suggested_total NUMERIC(12, 2) DEFAULT '0' NOT NULL;

UPDATE alembic_version SET version_num='004_smart_quote_pricing' WHERE alembic_version.version_num = '003_projects_history_pw_reset';

-- Running upgrade 004_smart_quote_pricing -> 005_quote_ai_analysis

ALTER TABLE quotes ADD COLUMN ai_analysis TEXT;

ALTER TABLE quotes ADD COLUMN ai_analyzed_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE alembic_version SET version_num='005_quote_ai_analysis' WHERE alembic_version.version_num = '004_smart_quote_pricing';

-- Running upgrade 005_quote_ai_analysis -> 006_quote_items

CREATE TABLE quote_items (
    id SERIAL NOT NULL, 
    quote_id INTEGER NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    description TEXT, 
    quantity NUMERIC(10, 2) DEFAULT '1' NOT NULL, 
    width NUMERIC(10, 2), 
    height NUMERIC(10, 2), 
    depth NUMERIC(10, 2), 
    unit_price NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    subtotal NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(quote_id) REFERENCES quotes (id) ON DELETE CASCADE
);

CREATE INDEX ix_quote_items_quote_id ON quote_items (quote_id);

UPDATE alembic_version SET version_num='006_quote_items' WHERE alembic_version.version_num = '005_quote_ai_analysis';

-- Running upgrade 006_quote_items -> 007_align_model_indexes

ALTER TABLE categories DROP CONSTRAINT categories_name_key;

CREATE UNIQUE INDEX ix_categories_name ON categories (name);

ALTER TABLE password_reset_tokens DROP CONSTRAINT password_reset_tokens_token_hash_key;

ALTER TABLE refresh_tokens DROP CONSTRAINT refresh_tokens_token_jti_key;

ALTER TABLE users DROP CONSTRAINT users_email_key;

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_customers_email ON customers (email);

CREATE INDEX ix_customers_name ON customers (name);

CREATE INDEX ix_products_category_id ON products (category_id);

CREATE INDEX ix_products_name ON products (name);

CREATE INDEX ix_quotes_customer_id ON quotes (customer_id);

CREATE INDEX ix_quotes_status ON quotes (status);

ALTER TABLE quotes ALTER COLUMN updated_at SET NOT NULL;

UPDATE alembic_version SET version_num='007_align_model_indexes' WHERE alembic_version.version_num = '006_quote_items';

-- Running upgrade 007_align_model_indexes -> 008_project_quote_link

ALTER TABLE projects ADD COLUMN quote_id INTEGER;

ALTER TABLE projects ADD CONSTRAINT fk_projects_quote_id_quotes FOREIGN KEY(quote_id) REFERENCES quotes (id) ON DELETE SET NULL;

CREATE UNIQUE INDEX ix_projects_quote_id ON projects (quote_id);

UPDATE alembic_version SET version_num='008_project_quote_link' WHERE alembic_version.version_num = '007_align_model_indexes';

-- Running upgrade 008_project_quote_link -> 009_materials_production_costs

CREATE TABLE suppliers (
    id SERIAL NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    contact_name VARCHAR(160), 
    phone VARCHAR(40), 
    email VARCHAR(320), 
    notes TEXT, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_suppliers_name ON suppliers (name);

CREATE INDEX ix_suppliers_is_active ON suppliers (is_active);

CREATE TABLE materials (
    id SERIAL NOT NULL, 
    supplier_id INTEGER, 
    name VARCHAR(180) NOT NULL, 
    kind VARCHAR(40) NOT NULL, 
    unit VARCHAR(30) DEFAULT 'un' NOT NULL, 
    unit_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    waste_percent NUMERIC(5, 2) DEFAULT '0' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL
);

CREATE INDEX ix_materials_supplier_id ON materials (supplier_id);

CREATE INDEX ix_materials_name ON materials (name);

CREATE INDEX ix_materials_kind ON materials (kind);

CREATE INDEX ix_materials_is_active ON materials (is_active);

CREATE TABLE project_costs (
    id SERIAL NOT NULL, 
    project_id INTEGER NOT NULL, 
    material_id INTEGER, 
    category VARCHAR(40) NOT NULL, 
    description VARCHAR(500) NOT NULL, 
    quantity NUMERIC(12, 3) DEFAULT '1' NOT NULL, 
    unit_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    total_cost NUMERIC(12, 2) DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(material_id) REFERENCES materials (id) ON DELETE SET NULL
);

CREATE INDEX ix_project_costs_project_id ON project_costs (project_id);

CREATE INDEX ix_project_costs_material_id ON project_costs (material_id);

CREATE INDEX ix_project_costs_category ON project_costs (category);

UPDATE alembic_version SET version_num='009_materials_production_costs' WHERE alembic_version.version_num = '008_project_quote_link';

-- Running upgrade 009_materials_production_costs -> 010_bootstrap_admin

UPDATE alembic_version SET version_num='010_bootstrap_admin' WHERE alembic_version.version_num = '009_materials_production_costs';

-- Running upgrade 010_bootstrap_admin -> 011_multitenant_foundation

CREATE TABLE tenants (
    id SERIAL NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    slug VARCHAR(180) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_tenants_name ON tenants (name);

CREATE UNIQUE INDEX ix_tenants_slug ON tenants (slug);

INSERT INTO tenants (name, slug, is_active)
            VALUES ('Multi-Marcenarias — Base existente', 'legacy-default', TRUE);

ALTER TABLE users ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_users_tenant_id ON users (tenant_id);

ALTER TABLE users ADD CONSTRAINT fk_users_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE SET NULL;

UPDATE users SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE activities ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_activities_tenant_id ON activities (tenant_id);

ALTER TABLE activities ADD CONSTRAINT fk_activities_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE activities SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE activities ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE categories ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_categories_tenant_id ON categories (tenant_id);

ALTER TABLE categories ADD CONSTRAINT fk_categories_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE categories SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE categories ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE customers ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_customers_tenant_id ON customers (tenant_id);

ALTER TABLE customers ADD CONSTRAINT fk_customers_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE customers SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE customers ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE materials ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_materials_tenant_id ON materials (tenant_id);

ALTER TABLE materials ADD CONSTRAINT fk_materials_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE materials SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE materials ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE products ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_products_tenant_id ON products (tenant_id);

ALTER TABLE products ADD CONSTRAINT fk_products_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE products SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE products ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE project_costs ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_project_costs_tenant_id ON project_costs (tenant_id);

ALTER TABLE project_costs ADD CONSTRAINT fk_project_costs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE project_costs SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE project_costs ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE projects ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_projects_tenant_id ON projects (tenant_id);

ALTER TABLE projects ADD CONSTRAINT fk_projects_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE projects SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE projects ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE quote_items ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_quote_items_tenant_id ON quote_items (tenant_id);

ALTER TABLE quote_items ADD CONSTRAINT fk_quote_items_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE quote_items SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE quote_items ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE quotes ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_quotes_tenant_id ON quotes (tenant_id);

ALTER TABLE quotes ADD CONSTRAINT fk_quotes_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE quotes SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE quotes ALTER COLUMN tenant_id SET NOT NULL;

ALTER TABLE suppliers ADD COLUMN tenant_id INTEGER;

CREATE INDEX ix_suppliers_tenant_id ON suppliers (tenant_id);

ALTER TABLE suppliers ADD CONSTRAINT fk_suppliers_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

UPDATE suppliers SET tenant_id = (SELECT id FROM tenants WHERE slug = 'legacy-default');

ALTER TABLE suppliers ALTER COLUMN tenant_id SET NOT NULL;

DROP INDEX ix_categories_name;

CREATE INDEX ix_categories_name ON categories (name);

ALTER TABLE categories ADD CONSTRAINT uq_categories_tenant_name UNIQUE (tenant_id, name);

UPDATE alembic_version SET version_num='011_multitenant_foundation' WHERE alembic_version.version_num = '010_bootstrap_admin';

-- Running upgrade 011_multitenant_foundation -> 012_saas_tenant_profile

ALTER TABLE tenants ADD COLUMN plan_code VARCHAR(40) DEFAULT 'starter' NOT NULL;

ALTER TABLE tenants ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL;

UPDATE alembic_version SET version_num='012_saas_tenant_profile' WHERE alembic_version.version_num = '011_multitenant_foundation';

-- Running upgrade 012_saas_tenant_profile -> 013_commercial_saas

CREATE TABLE subscriptions (
    id SERIAL NOT NULL, 
    tenant_id INTEGER NOT NULL, 
    provider VARCHAR(40) DEFAULT 'manual' NOT NULL, 
    provider_customer_id VARCHAR(180), 
    provider_subscription_id VARCHAR(180), 
    plan_code VARCHAR(40) DEFAULT 'starter' NOT NULL, 
    status VARCHAR(40) DEFAULT 'trialing' NOT NULL, 
    current_period_end TIMESTAMP WITHOUT TIME ZONE, 
    trial_end TIMESTAMP WITHOUT TIME ZONE, 
    cancel_at_period_end BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_subscriptions_tenant_id UNIQUE (tenant_id), 
    CONSTRAINT uq_subscriptions_provider_customer_id UNIQUE (provider_customer_id), 
    CONSTRAINT uq_subscriptions_provider_subscription_id UNIQUE (provider_subscription_id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_subscriptions_tenant_id ON subscriptions (tenant_id);

CREATE INDEX ix_subscriptions_status ON subscriptions (status);

CREATE TABLE usage_counters (
    id SERIAL NOT NULL, 
    tenant_id INTEGER NOT NULL, 
    metric VARCHAR(80) NOT NULL, 
    period VARCHAR(7) NOT NULL, 
    quantity INTEGER DEFAULT '0' NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_usage_tenant_metric_period UNIQUE (tenant_id, metric, period), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_usage_counters_tenant_id ON usage_counters (tenant_id);

CREATE INDEX ix_usage_counters_period ON usage_counters (period);

UPDATE alembic_version SET version_num='013_commercial_saas' WHERE alembic_version.version_num = '012_saas_tenant_profile';

-- Running upgrade 013_commercial_saas -> 014_guided_onboarding

ALTER TABLE tenants ADD COLUMN phone VARCHAR(40);

ALTER TABLE tenants ADD COLUMN city VARCHAR(100);

ALTER TABLE tenants ADD COLUMN state VARCHAR(40);

ALTER TABLE tenants ADD COLUMN document VARCHAR(30);

ALTER TABLE tenants ADD COLUMN default_profit_margin NUMERIC(5, 2) DEFAULT '30.00' NOT NULL;

ALTER TABLE tenants ADD COLUMN onboarding_step INTEGER DEFAULT '1' NOT NULL;

ALTER TABLE tenants ADD COLUMN onboarding_completed BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE tenants ADD COLUMN onboarding_completed_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE alembic_version SET version_num='014_guided_onboarding' WHERE alembic_version.version_num = '013_commercial_saas';

-- Running upgrade 014_guided_onboarding -> 015_trial_30_days

INSERT INTO subscriptions (
                tenant_id,
                provider,
                plan_code,
                status,
                trial_end,
                cancel_at_period_end,
                created_at,
                updated_at
            )
            SELECT
                tenants.id,
                'manual',
                tenants.plan_code,
                'trialing',
                (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + INTERVAL '30 days',
                false,
                CURRENT_TIMESTAMP AT TIME ZONE 'UTC',
                CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
            FROM tenants
            WHERE NOT EXISTS (
                SELECT 1
                FROM subscriptions
                WHERE subscriptions.tenant_id = tenants.id
            );

UPDATE subscriptions
            SET trial_end = (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + INTERVAL '30 days',
                updated_at = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
            WHERE status = 'trialing'
              AND trial_end IS NULL;

UPDATE alembic_version SET version_num='015_trial_30_days' WHERE alembic_version.version_num = '014_guided_onboarding';

-- Running upgrade 015_trial_30_days -> 016_ai_automation

CREATE TABLE ai_usage (
    id SERIAL NOT NULL, 
    operation VARCHAR(40) NOT NULL, 
    provider VARCHAR(30) NOT NULL, 
    model VARCHAR(120), 
    result VARCHAR(30) NOT NULL, 
    error_code VARCHAR(40), 
    duration_ms INTEGER NOT NULL, 
    consumption INTEGER NOT NULL, 
    request_id VARCHAR(64), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    tenant_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_usage_tenant_created ON ai_usage (tenant_id, created_at);

CREATE INDEX ix_ai_usage_tenant_id ON ai_usage (tenant_id);

CREATE TABLE automation_jobs (
    id SERIAL NOT NULL, 
    event_type VARCHAR(80) NOT NULL, 
    payload JSON NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    attempts INTEGER NOT NULL, 
    max_attempts INTEGER NOT NULL, 
    idempotency_key VARCHAR(180) NOT NULL, 
    request_id VARCHAR(64), 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    available_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    processed_at TIMESTAMP WITHOUT TIME ZONE, 
    last_error VARCHAR(80), 
    tenant_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_automation_status CHECK (status IN ('pending', 'retry', 'completed', 'failed')), 
    CONSTRAINT ck_automation_attempts CHECK (attempts >= 0 AND max_attempts > 0), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_automation_tenant_key UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ix_automation_due ON automation_jobs (status, available_at, id);

CREATE INDEX ix_automation_jobs_tenant_id ON automation_jobs (tenant_id);

ALTER TABLE activities ADD COLUMN idempotency_key VARCHAR(180);

ALTER TABLE activities ADD CONSTRAINT uq_activity_tenant_key UNIQUE (tenant_id, idempotency_key);

ALTER TABLE project_costs ADD COLUMN idempotency_key VARCHAR(128);

ALTER TABLE project_costs ADD COLUMN request_fingerprint VARCHAR(64);

ALTER TABLE project_costs ADD CONSTRAINT uq_cost_tenant_key UNIQUE (tenant_id, idempotency_key);

ALTER TABLE quotes ADD COLUMN technical_brief JSON;

ALTER TABLE quotes ADD COLUMN human_reviewed BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE quotes ALTER COLUMN human_reviewed DROP DEFAULT;

ALTER TABLE quotes ADD COLUMN idempotency_key VARCHAR(128);

ALTER TABLE quotes ADD COLUMN request_fingerprint VARCHAR(64);

ALTER TABLE quotes ADD CONSTRAINT uq_quote_tenant_key UNIQUE (tenant_id, idempotency_key);

ALTER TABLE subscriptions ADD COLUMN provider_event_created INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE subscriptions ALTER COLUMN provider_event_created DROP DEFAULT;

UPDATE alembic_version SET version_num='016_ai_automation' WHERE alembic_version.version_num = '015_trial_30_days';

-- Running upgrade 016_ai_automation -> 017_customer_portal

CREATE TABLE customer_portal_accounts (
    id SERIAL NOT NULL, 
    customer_id INTEGER NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255), 
    is_active BOOLEAN NOT NULL, 
    invitation_token_hash VARCHAR(64), 
    invitation_expires_at TIMESTAMP WITHOUT TIME ZONE, 
    reset_token_hash VARCHAR(64), 
    reset_expires_at TIMESTAMP WITHOUT TIME ZONE, 
    last_login_at TIMESTAMP WITHOUT TIME ZONE, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    tenant_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    UNIQUE (invitation_token_hash), 
    UNIQUE (reset_token_hash), 
    CONSTRAINT uq_customer_portal_customer UNIQUE (tenant_id, customer_id), 
    CONSTRAINT uq_customer_portal_email UNIQUE (tenant_id, email)
);

CREATE INDEX ix_customer_portal_accounts_customer_id ON customer_portal_accounts (customer_id);

CREATE INDEX ix_customer_portal_accounts_email ON customer_portal_accounts (email);

CREATE INDEX ix_customer_portal_accounts_tenant_id ON customer_portal_accounts (tenant_id);

CREATE TABLE customer_portal_messages (
    id SERIAL NOT NULL, 
    customer_id INTEGER NOT NULL, 
    quote_id INTEGER, 
    project_id INTEGER, 
    author_type VARCHAR(20) NOT NULL, 
    body TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    tenant_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_customer_portal_message_author CHECK (author_type IN ('customer', 'staff')), 
    FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE SET NULL, 
    FOREIGN KEY(quote_id) REFERENCES quotes (id) ON DELETE SET NULL, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_customer_portal_messages_created_at ON customer_portal_messages (created_at);

CREATE INDEX ix_customer_portal_messages_customer_id ON customer_portal_messages (customer_id);

CREATE INDEX ix_customer_portal_messages_project_id ON customer_portal_messages (project_id);

CREATE INDEX ix_customer_portal_messages_quote_id ON customer_portal_messages (quote_id);

CREATE INDEX ix_customer_portal_messages_tenant_id ON customer_portal_messages (tenant_id);

UPDATE alembic_version SET version_num='017_customer_portal' WHERE alembic_version.version_num = '016_ai_automation';

COMMIT;

