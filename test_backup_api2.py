from app.core.database import SessionLocal
from app.services.backup_service import backup_service
from app.repositories.usuario_repository import UsuarioRepository

db = SessionLocal()
try:
    repo = UsuarioRepository(db)
    user = repo.get_by_username('joshi_0211')
    res = backup_service.crear_backup_bd(db, actor=user)
    print(res)
except Exception as e:
    print('ERR')
    import traceback
    traceback.print_exc()
finally:
    db.close()
