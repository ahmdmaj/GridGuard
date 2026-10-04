import os
import ast
import glob

def test_air_gap_preserved() -> None:
    """
    Ensures that the intelligence layer does not directly import anything from the physical layer.
    """
    intelligence_dir = os.path.join(os.path.dirname(__file__), "..", "intelligence")
    python_files = glob.glob(os.path.join(intelligence_dir, "**", "*.py"), recursive=True)
    
    for file_path in python_files:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=file_path)
            except SyntaxError:
                continue
                
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("physical."), f"Air gap violation in {file_path}: imports {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert not node.module.startswith("physical"), f"Air gap violation in {file_path}: imports from {node.module}"
