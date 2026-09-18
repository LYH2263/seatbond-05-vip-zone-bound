import os

# 测试用内存 sqlite，无需 postgres；各用例自行建表并覆盖 get_db。
os.environ.setdefault("DATABASE_URL", "sqlite://")
