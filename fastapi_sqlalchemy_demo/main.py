# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from sqlalchemy.future import select
from database import engine, Base, get_db, AsyncSessionLocal
from models import TaskModel, UserModel
from schemas import TaskCreate, TaskResponse, UserResponse, ArchivadoResponse

# Evento de inicio para crear las tablas automáticamente
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Si no existe ningún usuario, se crea el usuario único por defecto
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel))
        if result.scalars().first() is None:
            session.add(UserModel(username="admin", nombre="Administrador"))
            await session.commit()
    yield

# Devuelve el usuario único del sistema
async def get_usuario_unico(db: AsyncSession) -> UserModel:
    result = await db.execute(select(UserModel).order_by(UserModel.id))
    return result.scalars().first()

app = FastAPI(
    title="FastAPI con SQLAlchemy 2.0",
    description="Ejemplo práctico de integración asíncrona",
    version="1.0.0",
    lifespan=lifespan
)

# 0. Obtener el usuario único (no se permite crear otros usuarios)
@app.get("/usuario", response_model=UserResponse)
async def read_usuario(db: AsyncSession = Depends(get_db)):
    return await get_usuario_unico(db)

# 1. Crear una Tarea (CREATE), asignada automáticamente al usuario único
@app.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, db: AsyncSession = Depends(get_db)):
    usuario = await get_usuario_unico(db)
    db_task = TaskModel(
        title=task.title,
        description=task.description,
        completed=task.completed,
        user_id=usuario.id
    )
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task

# 2. Listar Tareas (READ - List). Por defecto no incluye las archivadas
@app.get("/tasks/", response_model=list[TaskResponse])
async def read_tasks(
    skip: int = 0,
    limit: int = 10,
    incluir_archivadas: bool = False,
    db: AsyncSession = Depends(get_db)
):
    query = select(TaskModel)
    if not incluir_archivadas:
        query = query.where(TaskModel.archived == False)
    result = await db.execute(query.offset(skip).limit(limit))
    tasks = result.scalars().all()
    return list(tasks)

# 3. Obtener una Tarea por ID (READ - Detail)
@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def read_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    return task

# 4. Actualizar una Tarea (UPDATE)
@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_data: TaskCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    
    task.title = task_data.title
    task.description = task_data.description
    task.completed = task_data.completed
    
    await db.commit()
    await db.refresh(task)
    return task

# 5. Eliminar una Tarea (DELETE)
@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    
    await db.delete(task)
    await db.commit()
    return None

# 6. Marcar una Tarea como terminada
@app.patch("/tasks/{task_id}/completar", response_model=TaskResponse)
async def complete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")

    task.completed = True

    await db.commit()
    await db.refresh(task)
    return task

# 7. Archivar una Tarea (solo si está terminada)
@app.patch("/tasks/{task_id}/archivar", response_model=TaskResponse)
async def archive_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada")
    if not task.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden archivar tareas terminadas"
        )

    task.archived = True

    await db.commit()
    await db.refresh(task)
    return task

# 8. Archivar de una vez todas las Tareas terminadas
@app.post("/tasks/archivar-terminadas", response_model=ArchivadoResponse)
async def archive_completed_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        update(TaskModel)
        .where(TaskModel.completed == True, TaskModel.archived == False)
        .values(archived=True)
    )
    await db.commit()
    return ArchivadoResponse(archivadas=result.rowcount)
