from sentence_transformers import SentenceTransformer

print("Downloading model...")

model = SentenceTransformer("model/all-MiniLM-L6-v2")

print("Model downloaded successfully!")