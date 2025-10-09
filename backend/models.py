from sqlalchemy import (Column, Integer, String, Float, ForeignKey, 
                        create_engine, DateTime)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# --- INICIO DE LA CORRECCIÓN ---
# Añadimos el modelo 'Customer' que faltaba.
# Esto permite a SQLAlchemy crear la tabla 'customers' y gestionar la relación
# con la tabla 'orders' a través de la llave foránea 'customer_id'.
class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, unique=True, nullable=False) # WhatsApp ID
    name = Column(String)
    address = Column(String)
    orders = relationship("Order", back_populates="customer")
# --- FIN DE LA CORRECCIÓN ---

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

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    business_id = Column(Integer, ForeignKey('businesses.id'), nullable=False)
    status = Column(String, default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    total_price = Column(Float)
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    business = relationship("Business", back_populates="orders")

class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Float, nullable=False)
    price_at_purchase = Column(Float, nullable=False)
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

class Business(Base):
    __tablename__ = 'businesses'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    whatsapp_number = Column(String, unique=True, nullable=False)
    whatsapp_number_id = Column(String, unique=True, nullable=True)
    business_type = Column(String, nullable=False)
    personality_description = Column(String)
    products = relationship("Product", back_populates="business")
    orders = relationship("Order", back_populates="business")
