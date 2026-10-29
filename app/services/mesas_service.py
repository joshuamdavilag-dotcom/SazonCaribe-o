from http.client import HTTPException
from select import select

from pytest import Session
from app.models.salon import Mesa
from app.models.salon import Mesa

class MesaService:
    """Servicio para manejar la lógica de negocio relacionada con las mesas."""

    def __init__(self, db: Session):
        self.db = db    

def fusionar_mesas(db: Session, mesa_id_1: int, mesa_id_2: int, color: str = "#2A9D8F"):
    mesa1 = db.get(Mesa, mesa_id_1)
    mesa2 = db.get(Mesa, mesa_id_2)
    
    if not mesa1 or not mesa2:
        raise HTTPException(status_code=404, detail="Una de las mesas no existe.")
        
    # Ambas deben estar ocupadas o se unifican sus comandas
    # Vinculamos la mesa 2 a la mesa 1 (o creamos un identificador de grupo)
    mesa2.mesa_fusionada_id = mesa1.id
    mesa1.color_fusion = color
    mesa2.color_fusion = color
    
    # Unificar las órdenes activas si tienen cuentas separadas, 
    # o asociar la comanda para que apunte a ambas mesas.
    db.commit()
    return {"mensaje": f"Mesas {mesa1.numero} y {mesa2.numero} fusionadas correctamente."}

def separar_mesas(db: Session, mesa_id_1: int, mesa_id_2: int):
    mesa1 = db.get(Mesa, mesa_id_1)
    mesa2 = db.get(Mesa, mesa_id_2)
    
    if not mesa1 or not mesa2:
        raise HTTPException(status_code=404, detail="Una de las mesas no existe.")
        
    # Separar las mesas
    mesa2.mesa_fusionada_id = None
    mesa1.color_fusion = None
    mesa2.color_fusion = None
    
    # Si hay órdenes compartidas, se deben separar o duplicar según la lógica del negocio.
    db.commit()
    return {"mensaje": f"Mesas {mesa1.numero} y {mesa2.numero} separadas correctamente."}

def obtener_mesas_fusionadas(db: Session, mesa_id: int):
    mesa = db.get(Mesa, mesa_id)
    if not mesa:
        raise HTTPException(status_code=404, detail="La mesa no existe.")
    
    # Obtener todas las mesas que están fusionadas con la mesa dada
    statement = select(Mesa).where(Mesa.mesa_fusionada_id == mesa.id)
    mesas_fusionadas = db.execute(statement).scalars().all()
    
    return mesas_fusionadas

def obtener_mesas_fusionadas_por_color(db: Session, color: str):
    # Obtener todas las mesas que tienen el mismo color de fusión
    statement = select(Mesa).where(Mesa.color_fusion == color)
    mesas_fusionadas = db.execute(statement).scalars().all()
    
    return mesas_fusionadas

def fucionar_mas_mesas(db: Session, mesa_ids: list[int], color: str = "#2A9D8F"):
    if len(mesa_ids) < 2:
        raise HTTPException(status_code=400, detail="Se necesitan al menos dos mesas para fusionar.")
    
    mesas = [db.get(Mesa, mesa_id) for mesa_id in mesa_ids]
    
    if any(mesa is None for mesa in mesas):
        raise HTTPException(status_code=404, detail="Una de las mesas no existe.")
    
    # Tomamos la primera mesa como principal
    mesa_principal = mesas[0]
    
    for mesa in mesas[1:]:
        mesa.mesa_fusionada_id = mesa_principal.id
        mesa.color_fusion = color
    
    mesa_principal.color_fusion = color
    
    db.commit()
    return {"mensaje": f"Mesas fusionadas correctamente bajo la mesa {mesa_principal.numero}."}

def separar_mas_mesas(db: Session, mesa_ids: list[int]):
    if len(mesa_ids) < 2:
        raise HTTPException(status_code=400, detail="Se necesitan al menos dos mesas para separar.")
    
    mesas = [db.get(Mesa, mesa_id) for mesa_id in mesa_ids]
    
    if any(mesa is None for mesa in mesas):
        raise HTTPException(status_code=404, detail="Una de las mesas no existe.")
    
    for mesa in mesas:
        mesa.mesa_fusionada_id = None
        mesa.color_fusion = None
    
    db.commit()
    return {"mensaje": "Mesas separadas correctamente."}

def obtener_mesas_fusionadas_por_mesa(db: Session, mesa_id: int):
    mesa = db.get(Mesa, mesa_id)
    if not mesa:
        raise HTTPException(status_code=404, detail="La mesa no existe.")
    
    # Obtener todas las mesas que están fusionadas con la mesa dada
    statement = select(Mesa).where(Mesa.mesa_fusionada_id == mesa.id)
    mesas_fusionadas = db.execute(statement).scalars().all()
    
    return mesas_fusionadas
