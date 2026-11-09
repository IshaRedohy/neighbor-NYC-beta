"""Opaque keyset cursors. Cursors never replace participant/eligibility checks."""
import base64
import json
from datetime import datetime
from uuid import UUID
from fastapi import HTTPException


def encode_cursor(row, field):
    return base64.urlsafe_b64encode(json.dumps([row[field].isoformat(), str(row['id'])]).encode()).decode().rstrip('=')


def decode_cursor(value):
    if not value:
        return None
    try:
        if len(value) > 256:
            raise ValueError()
        stamp, identifier = json.loads(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)))
        stamp = datetime.fromisoformat(stamp)
        if stamp.tzinfo is None:
            raise ValueError()
        return stamp, UUID(identifier)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(400, 'Invalid page cursor.')
