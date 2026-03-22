from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

model.save("model/all-MiniLM-L6-v2")

print("Model saved locally!")