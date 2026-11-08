"""Future Lambda entry point; no infrastructure is created by this module.

Package with Python 3.12 Linux dependencies and configure networking/secrets first.
Connection pools live for the warm execution environment, not one invocation.
"""
import os
from mangum import Mangum
from .core import db_open, PRODUCTION
from .main import app

if not PRODUCTION or os.getenv('DEMO_MODE') == 'true':
    raise RuntimeError('Lambda requires ENVIRONMENT=production and DEMO_MODE=false.')
db_open()
handler = Mangum(app, lifespan='off')
