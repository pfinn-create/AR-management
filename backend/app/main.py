from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import Base, engine
from app.models import *  # ensure all models are registered
from app.routers import auth, companies, users, invoices, customers, payments, emails, todos, reports
from app.models.company import Company, COMPANIES
from app.models.user import User, UserRole
from app.routers.auth import hash_password
from sqlalchemy.orm import Session


def _seed_companies(db: Session):
    for code in COMPANIES:
        exists = db.query(Company).filter(Company.code == code).first()
        if not exists:
            db.add(Company(code=code, name=code, default_payment_terms_days=30))
    db.commit()


def _seed_admin(db: Session):
    admin = db.query(User).filter(User.email == "admin@armanagement.com").first()
    if not admin:
        admin = User(
            email="admin@armanagement.com",
            full_name="AR Manager",
            hashed_password=hash_password("changeme123"),
            role=UserRole.ar_manager,
        )
        db.add(admin)
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        _seed_companies(db)
        _seed_admin(db)
    yield


app = FastAPI(
    title="AR Management Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(users.router)
app.include_router(invoices.router)
app.include_router(customers.router)
app.include_router(payments.router)
app.include_router(emails.router)
app.include_router(todos.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}
