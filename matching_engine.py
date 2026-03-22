from clip_engine import get_embedding, get_text_embedding, get_similarity
from text_matching import text_similarity

def match_items(lost, found):

    score = 0

    # IMAGE ↔ IMAGE
    if lost["image"] and found["image"]:
        emb1 = lost["embedding"]
        emb2 = found["embedding"]

        if emb1 and emb2:
            score = get_similarity(emb1, emb2)

    # TEXT ↔ IMAGE
    elif found["image"]:
        text_emb = get_text_embedding(lost["description"])
        img_emb = found["embedding"]

        if text_emb and img_emb:
            score = get_similarity(text_emb, img_emb)

    # TEXT ↔ TEXT
    else:
        score = text_similarity(
            lost["description"],
            found["description"]
        )

    return int(score)