from app.core.database import SessionLocal, Base
from app.services.backup_service import BACKUP_TABLE
from sqlalchemy import select
from app.models.gasto import CategoriaGasto

db = SessionLocal()
try:
    for table in Base.metadata.sorted_tables:
        if table.name == BACKUP_TABLE:
            continue
        if table.name == 'gastos':
            try:
                filas = [
                    {col: row[col] for col in row.keys()}
                    for row in db.execute(select(table)).mappings()
                ]
                print('ok', len(filas))
            except Exception as e2:
                print(e2)
                import traceback
                traceback.print_exc()
            break
except Exception as e:
    print(e)
    import traceback
    traceback.print_exc()
finally:
    db.close()
