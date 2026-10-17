"""Internet-hosted menu photography, kept separate from checkout and model data.

Unsplash photos are served directly by their image CDN, not downloaded locally.
Related latte variants share representative photography. These are menu
illustrations, not photographs of Stories Coffee's actual products.
"""
from __future__ import annotations


_PHOTOS = {
    "Almond Croissant": "1618111415112-793c80d2fb3b",
    "Americano": "1588716857257-8603edde1d83",
    "Avocado Toast": "1560055932-595dab110124",
    "Banana Bread": "1569762404472-026308ba6b64",
    "Blueberry Muffin": "1637087788517-c63086ec5b7e",
    "Brownie": "1461009312844-e80697a81cc7",
    "Butter Croissant": "1725545901708-27d59e5c4226",
    "Cappuccino": "1525629545813-e4e7ba89e506",
    "Caramel Latte": "1537286164997-b6a9bbac8b55",
    "Chai Latte": "1578899952107-9c390f1af1b7",
    "Cheesecake Slice": "1524351199678-941a58a3df50",
    "Chicken Pesto Sandwich": "1496113269490-84ffe1a410cb",
    "Chicken Salad Bowl": "1646487793655-bbf280273d2f",
    "Chocolate Cookie": "1519682214708-973477a2529a",
    "Chocolate Croissant": "1729033143644-125574b23abd",
    "Cinnamon Roll": "1756137945173-a68976d6a645",
    "Classic Matcha": "1708572727896-117b5ea25a86",
    "Coffee Frappe": "1750818287648-df4cb95966d5",
    "Cold Brew": "1747218622335-77b9bb8f76bb",
    "Egg Sandwich": "1623624100942-a84520ca001c",
    "English Breakfast Tea": "1564729867715-9b78b10a790e",
    "Espresso": "1579992357154-faf4bde95b3d",
    "Flat White": "1537286164997-b6a9bbac8b55",
    "Fresh Orange Juice": "1600271886742-f049cd451bba",
    "Frozen Yoghurt Cup": "1722061844644-c0149ed99624",
    "Granola Yoghurt": "1641494587136-eec74f1944ae",
    "Halloumi Wrap": "1760888548893-bc2f7e09e972",
    "Iced Americano": "1747218622335-77b9bb8f76bb",
    "Iced Latte": "1671759545218-831c32bfe92d",
    "Iced Matcha": "1749280447307-31a68eb38673",
    "Iced Mocha": "1643945007749-bd99ea43c047",
    "Lemonade": "1658397020402-1caac9bcff87",
    "Mint Tea": "1708658767790-8029f20906ac",
    "Quinoa Bowl": "1623428186429-e76984bf48ad",
    "Soup of the Day": "1603208614668-b35c95647eaf",
    "Spanish Latte": "1537286164997-b6a9bbac8b55",
    "Sparkling Water": "1696446370329-7e7e7a2935dc",
    "Still Water": "1606873088303-9a23efba7ab9",
    "Strawberry Matcha": "1751033390078-b605c8727fa4",
    "Tiramisu Cup": "1605621234603-421e591840cd",
    "Tuna Sandwich": "1672078857105-a1229a7033b8",
    "Turkey & Cheese Sandwich": "1496113269490-84ffe1a410cb",
    "Vanilla Latte": "1537286164997-b6a9bbac8b55",
}

# These two specific products use photos from their source product pages.
_OTHER_PHOTOS = {
    "Peach Iced Tea": "https://artfultea.com/cdn/shop/files/0-1_2f43135a-b317-47d8-8f56-5e79f8a4265f.jpg?width=640",
    "Pistachio Cookie": "https://acdn-us.mitiendanube.com/stores/528/608/products/bb90f4a3-e0eb-49b0-ba4c-121df557015a-e0ba645f23d31ea9bf17441156069938-640-0.webp",
}


def product_image_url(product: str) -> str:
    """Return a stable remote image URL without changing product identities."""
    if product in _OTHER_PHOTOS:
        return _OTHER_PHOTOS[product]
    photo = _PHOTOS.get(product, _PHOTOS["Cappuccino"])
    return f"https://images.unsplash.com/photo-{photo}?auto=format&fit=crop&w=640&h=480&q=80"
