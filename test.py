import pickle
from pathlib import Path

path = Path("plsql_Acc_backend/rag_data/examples_metadata.pkl")
with path.open("rb") as f:
    payload = pickle.load(f)

print(payload.keys())
print(len(payload["examples"]))
print(payload["examples"][0])
print(len(payload["embeddings"][0]))