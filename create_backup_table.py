from app.core.database import engine, Base
import app.models.backup

Base.metadata.create_all(bind=engine)
print('done')
