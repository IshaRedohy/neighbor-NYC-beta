CREATE TABLE IF NOT EXISTS zip_codes (
  zip text PRIMARY KEY CHECK (zip ~ '^[0-9]{5}$'),
  borough text NOT NULL, neighborhood text NOT NULL,
  lat double precision NOT NULL, lon double precision NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE, google_sub text UNIQUE,
  name text NOT NULL, zip text REFERENCES zip_codes(zip),
  occupation text NOT NULL DEFAULT '', workplace text NOT NULL DEFAULT '',
  bio text NOT NULL DEFAULT '', languages text[] NOT NULL DEFAULT '{}',
  cultures text[] NOT NULL DEFAULT '{}', countries text[] NOT NULL DEFAULT '{}',
  expertise text[] NOT NULL DEFAULT '{}', interests text[] NOT NULL DEFAULT '{}',
  needs text[] NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','suspended','deleted')),
  role text NOT NULL DEFAULT 'member' CHECK (role IN ('member','admin')),
  visible boolean NOT NULL DEFAULT true, demo boolean NOT NULL DEFAULT false,
  consent_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), form_id text NOT NULL,
  response_id text NOT NULL, email text NOT NULL, payload jsonb,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  member_id uuid REFERENCES members(id), created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(form_id,response_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash text PRIMARY KEY, member_id uuid NOT NULL REFERENCES members(id),
  expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sender_id uuid NOT NULL REFERENCES members(id), recipient_id uuid NOT NULL REFERENCES members(id),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','declined')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (sender_id <> recipient_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS conversation_pair ON conversations(LEAST(sender_id,recipient_id),GREATEST(sender_id,recipient_id));
CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid NOT NULL REFERENCES conversations(id),
  sender_id uuid NOT NULL REFERENCES members(id), body text NOT NULL CHECK(length(body) BETWEEN 1 AND 2000),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id,created_at);
CREATE TABLE IF NOT EXISTS conversation_reads (
  conversation_id uuid REFERENCES conversations(id), member_id uuid REFERENCES members(id),
  read_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(conversation_id,member_id)
);
CREATE TABLE IF NOT EXISTS blocks (
  blocker_id uuid REFERENCES members(id), blocked_id uuid REFERENCES members(id),
  created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(blocker_id,blocked_id),
  CHECK(blocker_id <> blocked_id)
);
CREATE TABLE IF NOT EXISTS reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), reporter_id uuid REFERENCES members(id),
  reported_id uuid REFERENCES members(id), reason text NOT NULL CHECK(length(reason) BETWEEN 5 AND 1000),
  status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS graph_outbox (
  member_id uuid PRIMARY KEY REFERENCES members(id), version bigint NOT NULL DEFAULT 1,
  attempts integer NOT NULL DEFAULT 0, available_at timestamptz NOT NULL DEFAULT now(),
  last_error text, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION queue_graph_sync() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO graph_outbox(member_id) VALUES(NEW.id)
  ON CONFLICT(member_id) DO UPDATE SET version=graph_outbox.version+1, attempts=0, available_at=now(), updated_at=now();
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS member_graph_sync ON members;
CREATE TRIGGER member_graph_sync AFTER INSERT OR UPDATE ON members FOR EACH ROW EXECUTE FUNCTION queue_graph_sync();
CREATE TABLE IF NOT EXISTS rate_limits (
  key text PRIMARY KEY, hits integer NOT NULL DEFAULT 1, window_start timestamptz NOT NULL DEFAULT now()
);
