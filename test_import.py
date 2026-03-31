#!/usr/bin/env python
import sys
from pathlib import Path

# Set up path
sys.path.insert(0, str(Path(__file__).parent / 'plsql_Acc_backend'))

try:
    from src.parser.generated.PlSqlListener import PlSqlListener
    print(f"Success! PlSqlListener type: {type(PlSqlListener)}")
    print(f"PlSqlListener bases: {PlSqlListener.__bases__}")
except Exception as e:
    print(f"Failed to import PlSqlListener: {type(e).__name__}: {e}")

try:
    from antlr4 import ParseTreeListener
    print(f"antlr4.ParseTreeListener: {ParseTreeListener}")
except Exception as e:
    print(f"Failed to import antlr4: {type(e).__name__}: {e}")
