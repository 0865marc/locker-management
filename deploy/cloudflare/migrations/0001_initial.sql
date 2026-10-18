-- D1 schema v1. Forward-only; apply with Wrangler migrations, never at startup.
PRAGMA foreign_keys=ON;

CREATE TABLE deliveries (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(id)=36 AND substr(id,9,1)='-' AND substr(id,14,1)='-' AND substr(id,19,1)='-' AND substr(id,24,1)='-' AND length(replace(id,'-',''))=32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'),
  tracking_number TEXT NOT NULL,
  carrier_code TEXT NOT NULL,
  recipient_name TEXT NOT NULL,
  recipient_phone TEXT,
  received_at TEXT NOT NULL CHECK (typeof(received_at)='text' AND substr(received_at,1,4) BETWEEN '0001' AND '9999' AND length(received_at)=27 AND substr(received_at,20,1)='.' AND substr(received_at,27,1)='Z' AND substr(received_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(received_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(received_at,1,19),'+0 seconds')=substr(received_at,1,19)),
  pickup_deadline_at TEXT CHECK (pickup_deadline_at IS NULL OR (typeof(pickup_deadline_at)='text' AND substr(pickup_deadline_at,1,4) BETWEEN '0001' AND '9999' AND length(pickup_deadline_at)=27 AND substr(pickup_deadline_at,20,1)='.' AND substr(pickup_deadline_at,27,1)='Z' AND substr(pickup_deadline_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(pickup_deadline_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(pickup_deadline_at,1,19),'+0 seconds')=substr(pickup_deadline_at,1,19))),
  status TEXT NOT NULL,
  collected_at TEXT CHECK (collected_at IS NULL OR (typeof(collected_at)='text' AND substr(collected_at,1,4) BETWEEN '0001' AND '9999' AND length(collected_at)=27 AND substr(collected_at,20,1)='.' AND substr(collected_at,27,1)='Z' AND substr(collected_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(collected_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(collected_at,1,19),'+0 seconds')=substr(collected_at,1,19))),
  returned_to_carrier_at TEXT CHECK (returned_to_carrier_at IS NULL OR (typeof(returned_to_carrier_at)='text' AND substr(returned_to_carrier_at,1,4) BETWEEN '0001' AND '9999' AND length(returned_to_carrier_at)=27 AND substr(returned_to_carrier_at,20,1)='.' AND substr(returned_to_carrier_at,27,1)='Z' AND substr(returned_to_carrier_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(returned_to_carrier_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(returned_to_carrier_at,1,19),'+0 seconds')=substr(returned_to_carrier_at,1,19))),
  CHECK ((status='AWAITING_PICKUP' AND collected_at IS NULL AND returned_to_carrier_at IS NULL) OR (status='COLLECTED' AND collected_at IS NOT NULL AND returned_to_carrier_at IS NULL) OR (status='RETURNED_TO_CARRIER' AND collected_at IS NULL AND returned_to_carrier_at IS NOT NULL)),
  CHECK (collected_at IS NULL OR collected_at>=received_at),
  CHECK (returned_to_carrier_at IS NULL OR returned_to_carrier_at>=received_at)
);
CREATE TABLE returns (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(id)=36 AND substr(id,9,1)='-' AND substr(id,14,1)='-' AND substr(id,19,1)='-' AND substr(id,24,1)='-' AND length(replace(id,'-',''))=32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'),
  tracking_number TEXT NOT NULL,
  carrier_code TEXT NOT NULL,
  sender_name TEXT,
  received_at TEXT NOT NULL CHECK (typeof(received_at)='text' AND substr(received_at,1,4) BETWEEN '0001' AND '9999' AND length(received_at)=27 AND substr(received_at,20,1)='.' AND substr(received_at,27,1)='Z' AND substr(received_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(received_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(received_at,1,19),'+0 seconds')=substr(received_at,1,19)),
  status TEXT NOT NULL,
  handed_over_at TEXT CHECK (handed_over_at IS NULL OR (typeof(handed_over_at)='text' AND substr(handed_over_at,1,4) BETWEEN '0001' AND '9999' AND length(handed_over_at)=27 AND substr(handed_over_at,20,1)='.' AND substr(handed_over_at,27,1)='Z' AND substr(handed_over_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(handed_over_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(handed_over_at,1,19),'+0 seconds')=substr(handed_over_at,1,19))),
  CHECK ((status='AWAITING_CARRIER' AND handed_over_at IS NULL) OR (status='HANDED_OVER' AND handed_over_at IS NOT NULL)),
  CHECK (handed_over_at IS NULL OR handed_over_at>=received_at)
);
CREATE TABLE lockers (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(id)=36 AND substr(id,9,1)='-' AND substr(id,14,1)='-' AND substr(id,19,1)='-' AND substr(id,24,1)='-' AND length(replace(id,'-',''))=32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'),
  location_id TEXT,
  active INTEGER NOT NULL  CHECK (typeof(active)='integer' AND active IN (0,1)),
  country_code TEXT,
  postal_code TEXT,
  province TEXT,
  city TEXT,
  street TEXT,
  street_number TEXT,
  latitude REAL,
  longitude REAL,
  revision INTEGER NOT NULL DEFAULT 0 CHECK (typeof(revision)='integer' AND revision BETWEEN 0 AND 9007199254740990),
  mutation_token TEXT NOT NULL DEFAULT '' CHECK (mutation_token='' OR (length(mutation_token)=36 AND substr(mutation_token,9,1)='-' AND substr(mutation_token,14,1)='-' AND substr(mutation_token,19,1)='-' AND substr(mutation_token,24,1)='-' AND length(replace(mutation_token,'-',''))=32 AND replace(mutation_token,'-','') NOT GLOB '*[^0-9a-f]*')),
  CHECK ((country_code IS NULL AND postal_code IS NULL AND province IS NULL AND city IS NULL AND street IS NULL AND street_number IS NULL) OR ((country_code IS NOT NULL AND postal_code IS NOT NULL AND province IS NOT NULL AND city IS NOT NULL AND street IS NOT NULL AND street_number IS NOT NULL) AND (country_code='ES' AND length(postal_code)=5 AND postal_code NOT GLOB '*[^0-9]*' AND province<>'' AND province=trim(province,char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)) AND city<>'' AND city=trim(city,char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)) AND street<>'' AND street=trim(street,char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288)) AND street_number<>'' AND street_number=trim(street_number,char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288))))),
  CHECK ((latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))
);
CREATE INDEX ix_lockers_location_id ON lockers(location_id);
CREATE TABLE locker_compartments (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(id)=36 AND substr(id,9,1)='-' AND substr(id,14,1)='-' AND substr(id,19,1)='-' AND substr(id,24,1)='-' AND length(replace(id,'-',''))=32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'),
  locker_id TEXT NOT NULL REFERENCES lockers(id) ON DELETE RESTRICT CHECK (length(locker_id)=36 AND substr(locker_id,9,1)='-' AND substr(locker_id,14,1)='-' AND substr(locker_id,19,1)='-' AND substr(locker_id,24,1)='-' AND length(replace(locker_id,'-',''))=32 AND replace(locker_id,'-','') NOT GLOB '*[^0-9a-f]*'),
  width_mm INTEGER NOT NULL CHECK (typeof(width_mm)='integer' AND width_mm BETWEEN 1 AND 2147483647),
  height_mm INTEGER NOT NULL CHECK (typeof(height_mm)='integer' AND height_mm BETWEEN 1 AND 2147483647),
  depth_mm INTEGER NOT NULL CHECK (typeof(depth_mm)='integer' AND depth_mm BETWEEN 1 AND 2147483647),
  enabled INTEGER NOT NULL  CHECK (typeof(enabled)='integer' AND enabled IN (0,1)),
  retired INTEGER NOT NULL DEFAULT 0 CHECK (typeof(retired)='integer' AND retired IN (0,1)),
  CHECK (NOT (retired=1 AND enabled=1))
);
CREATE INDEX ix_compartments_locker_id ON locker_compartments(locker_id);
CREATE TABLE locker_assignments (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(id)=36 AND substr(id,9,1)='-' AND substr(id,14,1)='-' AND substr(id,19,1)='-' AND substr(id,24,1)='-' AND length(replace(id,'-',''))=32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'),
  compartment_id TEXT NOT NULL REFERENCES locker_compartments(id) ON DELETE RESTRICT CHECK (length(compartment_id)=36 AND substr(compartment_id,9,1)='-' AND substr(compartment_id,14,1)='-' AND substr(compartment_id,19,1)='-' AND substr(compartment_id,24,1)='-' AND length(replace(compartment_id,'-',''))=32 AND replace(compartment_id,'-','') NOT GLOB '*[^0-9a-f]*'),
  delivery_id TEXT UNIQUE REFERENCES deliveries(id) ON DELETE RESTRICT,
  return_id TEXT UNIQUE REFERENCES returns(id) ON DELETE RESTRICT,
  width_mm INTEGER NOT NULL CHECK (typeof(width_mm)='integer' AND width_mm BETWEEN 1 AND 2147483647),
  height_mm INTEGER NOT NULL CHECK (typeof(height_mm)='integer' AND height_mm BETWEEN 1 AND 2147483647),
  depth_mm INTEGER NOT NULL CHECK (typeof(depth_mm)='integer' AND depth_mm BETWEEN 1 AND 2147483647),
  assigned_at TEXT NOT NULL CHECK (typeof(assigned_at)='text' AND substr(assigned_at,1,4) BETWEEN '0001' AND '9999' AND length(assigned_at)=27 AND substr(assigned_at,20,1)='.' AND substr(assigned_at,27,1)='Z' AND substr(assigned_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(assigned_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(assigned_at,1,19),'+0 seconds')=substr(assigned_at,1,19)),
  released_at TEXT CHECK (released_at IS NULL OR (typeof(released_at)='text' AND substr(released_at,1,4) BETWEEN '0001' AND '9999' AND length(released_at)=27 AND substr(released_at,20,1)='.' AND substr(released_at,27,1)='Z' AND substr(released_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(released_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(released_at,1,19),'+0 seconds')=substr(released_at,1,19))),
  CHECK ((delivery_id IS NOT NULL AND return_id IS NULL) OR (delivery_id IS NULL AND return_id IS NOT NULL)),
  CHECK (released_at IS NULL OR released_at>=assigned_at)
);
CREATE UNIQUE INDEX uq_assignments_active_compartment ON locker_assignments(compartment_id) WHERE released_at IS NULL;
CREATE TABLE shipping_quotations (
  id TEXT NOT NULL PRIMARY KEY CHECK (length(id)=36 AND substr(id,9,1)='-' AND substr(id,14,1)='-' AND substr(id,19,1)='-' AND substr(id,24,1)='-' AND length(replace(id,'-',''))=32 AND replace(id,'-','') NOT GLOB '*[^0-9a-f]*'),
  origin_country_code TEXT NOT NULL,
  origin_postal_code TEXT NOT NULL,
  destination_country_code TEXT NOT NULL,
  destination_postal_code TEXT NOT NULL,
  weight_grams INTEGER NOT NULL CHECK (typeof(weight_grams)='integer' AND weight_grams BETWEEN 1 AND 30000),
  width_mm INTEGER NOT NULL CHECK (typeof(width_mm)='integer' AND width_mm BETWEEN 1 AND 2000),
  height_mm INTEGER NOT NULL CHECK (typeof(height_mm)='integer' AND height_mm BETWEEN 1 AND 2000),
  depth_mm INTEGER NOT NULL CHECK (typeof(depth_mm)='integer' AND depth_mm BETWEEN 1 AND 2000),
  status TEXT NOT NULL,
  created_at TEXT NOT NULL CHECK (typeof(created_at)='text' AND substr(created_at,1,4) BETWEEN '0001' AND '9999' AND length(created_at)=27 AND substr(created_at,20,1)='.' AND substr(created_at,27,1)='Z' AND substr(created_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(created_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(created_at,1,19),'+0 seconds')=substr(created_at,1,19)),
  finished_at TEXT CHECK (finished_at IS NULL OR (typeof(finished_at)='text' AND substr(finished_at,1,4) BETWEEN '0001' AND '9999' AND length(finished_at)=27 AND substr(finished_at,20,1)='.' AND substr(finished_at,27,1)='Z' AND substr(finished_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%dT%H:%M:%S',substr(finished_at,1,19),'+0 seconds') IS NOT NULL AND strftime('%Y-%m-%dT%H:%M:%S',substr(finished_at,1,19),'+0 seconds')=substr(finished_at,1,19))),
  process_error_code TEXT,
  CHECK (origin_country_code='ES' AND destination_country_code='ES' AND length(origin_postal_code)=5 AND origin_postal_code NOT GLOB '*[^0-9]*' AND length(destination_postal_code)=5 AND destination_postal_code NOT GLOB '*[^0-9]*'),
  CHECK ((status IN ('PENDING','PROCESSING') AND finished_at IS NULL AND process_error_code IS NULL) OR (status='COMPLETED' AND finished_at IS NOT NULL AND process_error_code IS NULL) OR (status='FAILED' AND finished_at IS NOT NULL AND process_error_code IS NOT NULL AND process_error_code IN ('PUBLISH_ERROR','PROCESSING_ERROR'))),
  CHECK (finished_at IS NULL OR finished_at>=created_at)
);
CREATE TABLE shipping_provider_results (
  quotation_id TEXT NOT NULL REFERENCES shipping_quotations(id) CHECK (length(quotation_id)=36 AND substr(quotation_id,9,1)='-' AND substr(quotation_id,14,1)='-' AND substr(quotation_id,19,1)='-' AND substr(quotation_id,24,1)='-' AND length(replace(quotation_id,'-',''))=32 AND replace(quotation_id,'-','') NOT GLOB '*[^0-9a-f]*'),
  provider_code TEXT NOT NULL,
  status TEXT NOT NULL,
  error_code TEXT,
  PRIMARY KEY (quotation_id,provider_code),
  CHECK (provider_code<>'' AND provider_code=trim(provider_code,char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288))),
  CHECK ((status IN ('QUOTED','NOT_COVERED') AND error_code IS NULL) OR (status='FAILED' AND error_code IS NOT NULL AND error_code IN ('PROVIDER_ERROR','PROVIDER_TIMEOUT')))
);
CREATE TABLE shipping_offers (
  quotation_id TEXT NOT NULL  CHECK (length(quotation_id)=36 AND substr(quotation_id,9,1)='-' AND substr(quotation_id,14,1)='-' AND substr(quotation_id,19,1)='-' AND substr(quotation_id,24,1)='-' AND length(replace(quotation_id,'-',''))=32 AND replace(quotation_id,'-','') NOT GLOB '*[^0-9a-f]*'),
  provider_code TEXT NOT NULL,
  service_code TEXT NOT NULL,
  price_cents INTEGER NOT NULL CHECK (typeof(price_cents)='integer' AND price_cents BETWEEN 1 AND 2147483647),
  currency TEXT NOT NULL CHECK (currency='EUR'),
  transit_days_min INTEGER NOT NULL CHECK (typeof(transit_days_min)='integer' AND transit_days_min BETWEEN 1 AND 2147483647),
  transit_days_max INTEGER NOT NULL CHECK (typeof(transit_days_max)='integer' AND transit_days_max BETWEEN 1 AND 2147483647),
  PRIMARY KEY (quotation_id,provider_code,service_code),
  FOREIGN KEY (quotation_id,provider_code) REFERENCES shipping_provider_results(quotation_id,provider_code),
  CHECK (service_code<>'' AND service_code=trim(service_code,char(9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288))),
  CHECK (transit_days_max>=transit_days_min)
);
