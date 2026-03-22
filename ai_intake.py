import re

def extract_item_details(text):

    text = text.lower()

    colors = [
        "black","white","blue","red","green",
        "yellow","pink","orange","brown","grey"
    ]

    locations = [
        "library","canteen","parking","lab",
        "classroom","hostel","ground","gate"
    ]

    items = [
        "phone","mobile","earbuds","wallet","bottle",
        "bag","pouch","tiffin","charger","laptop",
        "calculator","umbrella","keys","documents",
        "id card","aadhar card","aadhaar card"
    ]

    color=None
    location=None
    title=None

    for c in colors:
        if c in text:
            color=c

    for l in locations:
        if l in text:
            location=l

    for i in items:
        if i in text:
            title=i

    if title is None:
        words=text.split()
        title=words[-1]

    description=f"{color or ''} {title}".strip()

    return {
        "title":title,
        "description":description,
        "location":location
    }