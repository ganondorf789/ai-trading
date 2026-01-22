"""
共享数据库实例
所有路由模块都从这里导入 db，避免重复初始化
"""
from database import TraderDatabase

# 全局共享的数据库实例
db = TraderDatabase()
