from app.core.database import SessionLocal, Base
from app.services.backup_service import backup_service
from sqlalchemy import select

db = SessionLocal()
try:
    for table in Base.metadata.sorted_tables:
        if table.name == backup_service.BACKUP_TABLE:
            continue
        if table.name == 'gastos':
            print('found')
            result = db.execute(select(table)).mappings()
            rows = list(result)
            print(len(rows))
            for row in rows:
                print(row)
            break
except Exception as e:
    print(e)
    import traceback
    traceback.print_exc()
finally:
    db.close()
