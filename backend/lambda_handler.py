from .runtime import load_secrets
load_secrets()
from mangum import Mangum
from .core import db_open
from .main import app

db_open()
# Mangum access logging is disabled: OAuth query strings and identities never enter logs.
import logging
logging.getLogger('mangum.http').setLevel(logging.WARNING)
handler = Mangum(app, lifespan='off')
