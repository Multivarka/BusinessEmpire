import time
from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    balance = Column(Integer, default=100)
    works_in_company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    employer_company = relationship("Company", foreign_keys=[works_in_company_id], back_populates="workers")
    own_company = relationship("Company", back_populates="owner", uselist=False, foreign_keys="Company.owner_id")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    owner_id = Column(BigInteger, ForeignKey("users.id"), unique=True)

    # НОВОЕ: Unix-timestamp времени последнего сбора прибыли
    last_collect = Column(Integer, default=lambda: int(time.time()))

    # НОВОЕ: Сколько монет приносит один раб в секунду (базово — 1 монета)
    income_per_worker = Column(Integer, default=1)

    owner = relationship("User", foreign_keys=[owner_id], back_populates="own_company")
    workers = relationship("User", foreign_keys=[User.works_in_company_id], back_populates="employer_company")