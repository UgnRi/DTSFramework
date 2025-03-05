#run.py
import os
import sys
from pathlib import Path


src_path = Path(__file__).parent / "src"
sys.path.append(str(src_path))


from main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())