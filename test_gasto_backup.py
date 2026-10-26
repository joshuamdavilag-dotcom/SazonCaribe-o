from app.core.database import SessionLocal, Base
from app.services.backup_service import BACKUP_TABLE, _serialize_value
from sqlalchemy import select

db = SessionLocal()
try:
    for table in Base.metadata.sorted_tables:
        if table.name == BACKUP_TABLE:
            continue
        if table.name == 'gastos':
            try:
                filas = [
                    {col: _serialize_value(row[col]) for col in row.keys()}
                    for row in db.execute(select(table)).mappings()
                ]
                print(len(filas))
            except Exception as e2:
                print('ERR')
                import traceback
                traceback.print_exc()
            break
except Exception as e:
    print(e)
    import traceback
    traceback.print_exc()
finally:
    db.close()
