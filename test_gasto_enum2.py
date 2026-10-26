from app.core.database import SessionLocal, Base
from app.services.backup_service import BACKUP_TABLE
from sqlalchemy import select
from app.services.backup_service import _serialize_value

db = SessionLocal()
try:
    for table in Base.metadata.sorted_tables:
        if table.name == BACKUP_TABLE:
            continue
        if table.name == 'gastos':
            try:
                result = db.execute(select(table)).mappings()
                filas = [
                    {col: row[col] for col in row.keys()}
                    for row in result
                ]
                filas_ser = [{k: _serialize_value(v) for k,v in f.items()} for f in filas]
                print('ok', len(filas_ser))
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
