import subprocess
import hashlib
import json
import datetime
import sys

# Cache git status at module load time so generated results don't mark themselves as dirty
_GIT_COMMIT = "unknown"
_GIT_DIRTY = False
try:
    _GIT_COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    _GIT_DIRTY = bool(status)
except Exception:
    pass

def get_provenance(config, seed=None):
    git_commit = _GIT_COMMIT
    git_dirty = _GIT_DIRTY
        
    sklearn_version = "unknown"
    try:
        import sklearn
        sklearn_version = sklearn.__version__
    except ImportError:
        pass
        
    def default_encoder(obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
        
    config_str = json.dumps(config, sort_keys=True, default=default_encoder)
    config_sha256 = hashlib.sha256(config_str.encode('utf-8')).hexdigest()
    
    # We must ensure config itself is serializable when returned
    clean_config = json.loads(config_str)
    
    return {
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "config": clean_config,
        "config_sha256": config_sha256,
        "seed": seed,
        "python_version": sys.version.split(" ")[0],
        "sklearn_version": sklearn_version,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
