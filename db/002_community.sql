CREATE TABLE IF NOT EXISTS posts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 author_id uuid NOT NULL REFERENCES members(id),
 kind text NOT NULL CHECK(kind IN ('need','offer','event')),
 title text NOT NULL, body text NOT NULL, tags text[] NOT NULL,
 zip text NOT NULL REFERENCES zip_codes(zip),
 starts_at timestamptz, venue text NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((kind='event') = (starts_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS posts_created ON posts(created_at DESC);
CREATE TABLE IF NOT EXISTS event_reads (
 member_id uuid REFERENCES members(id), post_id uuid REFERENCES posts(id) ON DELETE CASCADE,
 PRIMARY KEY(member_id,post_id)
);
