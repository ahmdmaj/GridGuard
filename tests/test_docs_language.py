import os
import re

FORBIDDEN_TERMS = [
    "flawless", "perfect", "guarantee", "absolute safety", 
    "mathematically concrete", "hardcore", "solved", 
    "bulletproof", "never fail", "never fails"
]

def test_docs_language():
    docs_dirs = ["docs", "."]
    
    found_forbidden = []
    
    for d in docs_dirs:
        for root, dirs, files in os.walk(d):
            if 'venv' in dirs:
                dirs.remove('venv')
            for file in files:
                if file.endswith(".md") and "GridGuard_Redesign_Spec.md" not in file and "execution plan.md" not in file:
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    for term in FORBIDDEN_TERMS:
                        if re.search(r'\b' + term + r'\b', content, re.IGNORECASE):
                            found_forbidden.append(f"Forbidden term '{term}' found in {filepath}")

    assert len(found_forbidden) == 0, "\n".join(found_forbidden)
