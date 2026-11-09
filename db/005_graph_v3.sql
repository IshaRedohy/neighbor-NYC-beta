-- Refresh existing projections for normalized occupations/skills; IDs and roles do not change.
INSERT INTO graph_outbox(member_id) SELECT id FROM members
ON CONFLICT(member_id) DO UPDATE SET version=graph_outbox.version+1, attempts=0, available_at=now(), updated_at=now();
