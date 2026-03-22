import torch
import clip
from PIL import Image
import numpy as np

device = "cpu"

model, preprocess = clip.load("ViT-B/32", device=device)


def get_embedding(image_path):

    image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)

    with torch.no_grad():
        image_features = model.encode_image(image)

    image_features = image_features / image_features.norm(dim=-1, keepdim=True)

    return image_features.cpu().numpy().flatten().tolist()


def get_text_embedding(text):

    tokens = clip.tokenize([text]).to(device)

    with torch.no_grad():
        text_features = model.encode_text(tokens)

    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    return text_features.cpu().numpy().flatten().tolist()


def get_similarity(vec1, vec2):

    v1 = np.array(vec1)
    v2 = np.array(vec2)

    similarity = np.dot(v1, v2) / (
        np.linalg.norm(v1) * np.linalg.norm(v2)
    )

    score = max(0, int(similarity * 100))

    return score