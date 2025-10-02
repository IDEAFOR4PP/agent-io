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
    availability_status = Column(String, nullable=False, default='UNCONFIRMED')
    business_id = Column(Integer, ForeignKey('businesses.id'), nullable=False)
    business = relationship("Business", back_populates="products")

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

class Business(Base):
    __tablename__ = 'businesses'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False) # Ej: "Ferretería Don Pepe"
    whatsapp_number = Column(String, unique=True, nullable=False) # El número que recibe los mensajes
    business_type = Column(String, nullable=False) # Ej: 'ferreteria', 'restaurante', 'abarrotes'
    
    # ¡Campo clave para la personalización del prompt!
    personality_description = Column(String) # Ej: "Un tono amigable y servicial, experto en herramientas."
    
    products = relationship("Product", back_populates="business")