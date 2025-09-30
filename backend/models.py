from sqlalchemy import (Column, Integer, String, Float, ForeignKey, 
                        create_engine, DateTime)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)

class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, nullable=False) # WhatsApp ID
    name = Column(String)
    address = Column(String)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    status = Column(String, default='pending') # pending, confirmed, delivered
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    total_price = Column(Float)
    customer = relationship("Customer")

class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Float, nullable=False)
    price_at_purchase = Column(Float, nullable=False)
    order = relationship("Order")
    product = relationship("Product")