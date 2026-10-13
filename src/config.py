import yaml
from pathlib import Path

def load_config(path="config.yaml"):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{path} not found. Copy config.example.yaml to config.yaml and edit it."
        )
    with p.open() as f:
        cfg = yaml.safe_load(f)

    required = ["search", "location", "compensation", "skills", "digest"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Config missing sections: {missing}")
    return cfg

if __name__ == "__main__":
    cfg = load_config()
    print(f"Loaded {len(cfg['search']['primary_titles'])} primary titles.")
