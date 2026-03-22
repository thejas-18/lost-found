from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


model = SentenceTransformer("all-MiniLM-L6-v2")


def get_text_embedding(text):

    if not text:
        text = ""

    embedding = model.encode(text)

    return embedding


def text_similarity(text1, text2):

    if not text1 or not text2:
        return 0

    emb1 = get_text_embedding(text1)
    emb2 = get_text_embedding(text2)

    score = cosine_similarity([emb1], [emb2])[0][0]

    percentage = int(score * 100)

    if percentage < 0:
        percentage = 0

    return percentage