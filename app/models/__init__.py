"""数据模型"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Channel(Base):
    """模型通道配置"""
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)  # 通道名称 (如 gpt-4o)
    display_name = Column(String(100))  # 显示名称
    provider = Column(String(50), nullable=False)  # openai/anthropic/google/local
    base_url = Column(String(500))  # API地址
    models = Column(JSON)  # 支持的模型列表
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 默认通道
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    keys = relationship("Key", back_populates="channel", cascade="all, delete-orphan")
    request_logs = relationship("RequestLog", back_populates="channel")


class Key(Base):
    """API密钥池"""
    __tablename__ = "keys"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    key_value = Column(String(500), nullable=False)  # 存储加密的密钥
    name = Column(String(100))  # 密钥名称/备注
    weight = Column(Integer, default=1)  # 权重
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)  # 被封禁
    request_count = Column(Integer, default=0)  # 使用次数
    error_count = Column(Integer, default=0)  # 错误次数
    last_used_at = Column(DateTime)
    last_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    channel = relationship("Channel", back_populates="keys")
    request_logs = relationship("RequestLog", back_populates="key")


class RequestLog(Base):
    """请求日志"""
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    key_id = Column(Integer, ForeignKey("keys.id"))
    model = Column(String(100), nullable=False)  # 请求的模型
    request_id = Column(String(100))  # 本地请求ID
    
    # Token统计
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # 性能指标
    latency_ms = Column(Float, default=0)  # 总延迟
    ttft_ms = Column(Float, default=0)  # 首个token响应时间
    first_token_at = Column(Float, default=0)  # 首个token时间戳
    
    # 状态
    status = Column(String(20), default="pending")  # pending/success/failed
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # 额外信息
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    request_body = Column(Text)  # 请求体（脱敏）
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    channel = relationship("Channel", back_populates="request_logs")
    key = relationship("Key", back_populates="request_logs")


class DailyStats(Base):
    """每日统计聚合"""
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    model = Column(String(100))
    date = Column(String(10))  # YYYY-MM-DD
    
    request_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    total_prompt_tokens = Column(Integer, default=0)
    total_completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    total_latency = Column(Float, default=0)
    avg_latency = Column(Float, default=0)
    total_ttft = Column(Float, default=0)
    avg_ttft = Column(Float, default=0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_daily_stats_channel_date', 'channel_id', 'date'),
    )