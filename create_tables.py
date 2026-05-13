import os
from sqlalchemy import create_engine
from app.db.base import Base
from app.models.user import User
from app.models.transaction import Transaction
from app.models.alert import Alert
from app.models.fraud_log import FraudLog
from app.models.forecast import Forecast
from app.models.virtual_account import VirtualAccount

engine = create_engine(os.environ['DATABASE_URL_SYNC'])
Base.metadata.create_all(engine)
print("Tables created successfully!")
