# schemas.py
from pydantic import BaseModel, ConfigDict

class UserResponse(BaseModel):
    id: int
    username: str
    nombre: str

    model_config = ConfigDict(from_attributes=True)

class TaskBase(BaseModel):
    title: str
    description: str | None = None
    completed: bool = False

class TaskCreate(TaskBase):
    pass

class TaskResponse(TaskBase):
    id: int
    archived: bool = False
    user_id: int

    # Configuración para permitir la lectura de modelos ORM directamente (equivalente a orm_mode en v1)
    model_config = ConfigDict(from_attributes=True)

# Respuesta de archivado masivo: cantidad de tareas archivadas
class ArchivadoResponse(BaseModel):
    archivadas: int
