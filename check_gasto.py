from app.core.database import SessionLocal
from sqlalchemy import select
from app.models import Gasto

db = SessionLocal()
try:
    rows = db.execute(select(Gasto)).scalars().all()
    print(len(rows))
    for r in rows:
        print(r.categoria, type(r.categoria))
except Exception as e:
    print('ERR')
    import traceback
    traceback.print_exc()
finally:
    db.close()
