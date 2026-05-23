import sys
import os

# 确保项目根目录在 sys.path 中（以便 "src" 可被导入）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.main import main

if __name__ == "__main__":
    main() 