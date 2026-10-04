import os
import re

FORBIDDEN_TERMS = [
    "flawless", "guarantee", "perfect", "solved", 
    "hardcore", "mathematically prove", "absolute safety", 
    "never fail", "bulletproof"
]

def test_docs_language():
    docs_dirs = ["docs", "."]
    
    found_forbidden = []
    
    for d in docs_dirs:
        for root, dirs, files in os.walk(d):
            # Exclude internal and evidence directories
            if 'venv' in dirs:
                dirs.remove('venv')
            if 'internal' in dirs and root == "docs":
                dirs.remove('internal')
            if 'evidence' in dirs and root == "docs":
                dirs.remove('evidence')
                
            for file in files:
                if file.endswith(".md"):
                    filepath = os.path.join(root, file)
                    # Skip README if it's in a subdirectory (just want the root README if scanning .)
                    if d == "." and root != ".":
                        continue
                    
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    for term in FORBIDDEN_TERMS:
                        if re.search(r'\b' + term + r'\b', content, re.IGNORECASE):
                            found_forbidden.append(f"Forbidden term '{term}' found in {filepath}")

    assert len(found_forbidden) == 0, "\n".join(found_forbidden)
