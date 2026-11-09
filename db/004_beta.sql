ALTER TABLE messages ADD COLUMN client_message_id uuid;
CREATE UNIQUE INDEX messages_retry ON messages(sender_id,client_message_id) WHERE client_message_id IS NOT NULL;
CREATE INDEX messages_cursor ON messages(conversation_id,created_at DESC,id DESC);
CREATE INDEX conversations_cursor ON conversations(updated_at DESC,id DESC);
CREATE TABLE matching_preferences (
 member_id uuid PRIMARY KEY REFERENCES members(id), shared_culture boolean NOT NULL DEFAULT false,
 updated_at timestamptz NOT NULL DEFAULT now()
);
-- Login identities exist independently of approved community memberships.
CREATE TABLE login_identities (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), issuer text NOT NULL, subject text NOT NULL,
 email text NOT NULL, member_id uuid REFERENCES members(id), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(issuer,subject)
);
CREATE TABLE applicant_sessions (
 token_hash text PRIMARY KEY, identity_id uuid NOT NULL REFERENCES login_identities(id),
 expires_at timestamptz NOT NULL
);
ALTER TABLE submissions ADD COLUMN identity_id uuid REFERENCES login_identities(id);
CREATE UNIQUE INDEX applicant_pending ON submissions(identity_id) WHERE status='pending' AND identity_id IS NOT NULL;
CREATE TABLE oauth_attempts (state_hash text PRIMARY KEY, expires_at timestamptz NOT NULL);
