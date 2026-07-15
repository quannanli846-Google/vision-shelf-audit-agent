-- Vision AI Shelf Audit - initial schema
-- Run this in the Supabase SQL editor (Project -> SQL Editor -> New query).

create extension if not exists "pgcrypto";

-- ============================================================================
-- accounts: stores/customer locations a field rep audits
-- ============================================================================
create table if not exists accounts (
    id          uuid primary key default gen_random_uuid(),
    store_name  text not null,
    created_at  timestamptz not null default now()
);

-- ============================================================================
-- products: small SKU reference catalog used for grounding vision output
-- ============================================================================
create table if not exists products (
    id           uuid primary key default gen_random_uuid(),
    brand        text not null,
    product_name text not null,
    size         text,
    aliases      text[] not null default '{}',
    created_at   timestamptz not null default now()
);

-- ============================================================================
-- audits: one row per uploaded media asset + its structured ShelfAudit result
-- ============================================================================
create table if not exists audits (
    id             uuid primary key default gen_random_uuid(),
    account_id     uuid not null references accounts(id) on delete cascade,
    media_url      text not null,
    media_type     text not null check (media_type in ('image', 'video')),
    status         text not null default 'uploaded'
                       check (status in ('uploaded', 'processing', 'completed', 'failed')),
    status_message text,
    audit_json     jsonb,
    error_message  text,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

create index if not exists idx_audits_account_id on audits(account_id);
create index if not exists idx_audits_status on audits(status);

-- keep updated_at fresh on every row change
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_audits_updated_at on audits;
create trigger trg_audits_updated_at
    before update on audits
    for each row
    execute function set_updated_at();

-- ============================================================================
-- Seed data: sample accounts
-- ============================================================================
insert into accounts (store_name) values
    ('Riverside Liquor & Wine'),
    ('Downtown Market #142'),
    ('Sunset Beverage Depot')
on conflict do nothing;

-- ============================================================================
-- Seed data: sample SKU catalog (beverage / alcohol)
-- ============================================================================
insert into products (brand, product_name, size, aliases) values
    ('Tito''s',       'Handmade Vodka',        '750ml', array['titos', 'titos vodka', 'handmade vodka']),
    ('Tito''s',       'Handmade Vodka',        '1.75L', array['titos 1.75', 'titos handle']),
    ('Grey Goose',    'Vodka',                 '750ml', array['greygoose', 'grey goose vodka']),
    ('Absolut',       'Vodka',                 '750ml', array['absolut vodka']),
    ('Smirnoff',      'No. 21 Vodka',          '750ml', array['smirnoff vodka', 'smirnoff no 21']),
    ('Jack Daniel''s','Old No. 7 Whiskey',     '750ml', array['jack daniels', 'jd', 'old no 7']),
    ('Jameson',       'Irish Whiskey',         '750ml', array['jameson whiskey', 'jameson irish']),
    ('Jim Beam',      'Kentucky Bourbon',      '750ml', array['jim beam bourbon']),
    ('Bacardi',       'Superior Rum',          '750ml', array['bacardi superior', 'bacardi white']),
    ('Captain Morgan','Original Spiced Rum',   '750ml', array['captain morgan spiced']),
    ('Patron',        'Silver Tequila',        '750ml', array['patron silver', 'patron tequila']),
    ('Casamigos',     'Blanco Tequila',        '750ml', array['casamigos blanco']),
    ('Corona',        'Extra',                 '12pk',  array['corona extra 12 pack', 'corona beer']),
    ('Bud Light',     'Lager',                 '12pk',  array['budlight', 'bud light beer']),
    ('Heineken',      'Lager',                 '12pk',  array['heineken beer', 'heineken lager']),
    ('White Claw',    'Hard Seltzer Variety',  '12pk',  array['white claw variety pack', 'whiteclaw']),
    ('Smirnoff Ice',  'Malt Beverage',         '6pk',   array['smirnoff ice 6 pack']),
    ('Coca-Cola',     'Classic',               '12pk cans', array['coke', 'coca cola classic']),
    ('Pepsi',         'Cola',                  '12pk cans', array['pepsi cola']),
    ('Topo Chico',    'Mineral Water',         '12pk',  array['topo chico sparkling water'])
on conflict do nothing;
