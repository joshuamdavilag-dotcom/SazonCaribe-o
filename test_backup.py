from app.core.database import SessionLocal
from app.services.backup_service import backup_service

db = SessionLocal()
try:
    res = backup_service.crear_backup_bd(db)
    print(res)
except Exception as e:
    print('ERR', e)
    import traceback
    traceback.print_exc()
finally:
    db.close()
