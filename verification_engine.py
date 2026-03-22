from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")

def calculate_ownership_score(lost_item, claim_data):

    score = 0

    emb1 = model.encode(lost_item["description"])
    emb2 = model.encode(claim_data["description"])

    similarity = float(util.cos_sim(emb1, emb2)[0][0])

    score += similarity * 40

    if lost_item["location"] == claim_data["location"]:
        score += 10

    if lost_item["title"] in claim_data["description"]:
        score += 30

    return int(score)