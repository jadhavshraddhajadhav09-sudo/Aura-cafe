import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

# Check for Groq Python Client
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

SYSTEM_PROMPT = """You are an expert AI POS assistant for a coffee shop and restaurant.
Your task is to analyze natural language customer food/drink orders and extract structured JSON data.

Rules:
1. Extract all items mentioned in the order text.
2. For each item, identify:
   - "item": Clear concise name of the item (e.g. "Iced Caramel Macchiato", "Blueberry Muffin", "Cheeseburger")
   - "size": Size if specified ("Small", "Medium", "Large", "Regular", or "Standard" if not mentioned)
   - "add_ons": Array of strings listing extra shots, milk choices, toppings, or modifications (e.g. ["Oat milk", "Extra espresso shot", "No onions"])
   - "price": Reasonable estimated price in USD (e.g. Coffee: $3.50-$6.00, Bakery: $3.00-$5.00, Meals: $8.00-$15.00, Add-ons: $0.50-$1.25)
3. Calculate subtotal, tax (estimated at 8%), and total_price.
4. Extract any special_instructions (e.g. "Extra hot", "Separate bags", "Less ice") or set to "None".
5. Provide a crisp 1-line summary of the order.

Return ONLY a valid JSON object strictly matching this schema:
{
  "summary": "String summary of order",
  "items": [
    {
      "item": "Item Name",
      "size": "Medium",
      "add_ons": ["Add-on 1", "Add-on 2"],
      "price": 5.50
    }
  ],
  "subtotal": 5.50,
  "tax": 0.44,
  "total_price": 5.94,
  "special_instructions": "Notes or None"
}
"""

def parse_order_with_groq(raw_text: str) -> dict:
    """Sends customer text to Groq API and parses the JSON order structure."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if GROQ_AVAILABLE and api_key and api_key != "your_groq_api_key_here":
        try:
            client = Groq(api_key=api_key)
            # Use Groq's high-speed Llama 3.3 70B model or fall back to Llama 3 8B
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Parse this customer order into JSON:\n\n\"{raw_text}\""}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            parsed = json.loads(content)
            parsed["source"] = "Groq LLM (llama-3.3-70b)"
            return sanitize_parsed_order(parsed)
        except Exception as e:
            print(f"[Groq API Error]: {e} - falling back to smart heuristic parser.")

    # Fallback / Demo Mode parser if API key is missing or failed
    return parse_order_mock_fallback(raw_text)


def sanitize_parsed_order(data: dict) -> dict:
    """Ensures expected schema fields exist and numerical fields are floats."""
    items = data.get("items", [])
    sanitized_items = []
    calculated_subtotal = 0.0

    for item in items:
        item_name = str(item.get("item", "Item")).strip()
        size = str(item.get("size", "Standard")).strip()
        add_ons = item.get("add_ons", [])
        if not isinstance(add_ons, list):
            add_ons = [str(add_ons)]
        
        try:
            price = round(float(item.get("price", 4.50)), 2)
        except (ValueError, TypeError):
            price = 4.50
        
        calculated_subtotal += price
        sanitized_items.append({
            "item": item_name,
            "size": size,
            "add_ons": add_ons,
            "price": price
        })

    subtotal = round(float(data.get("subtotal", calculated_subtotal)), 2)
    tax = round(float(data.get("tax", round(subtotal * 0.08, 2))), 2)
    total_price = round(float(data.get("total_price", round(subtotal + tax, 2))), 2)

    return {
        "summary": data.get("summary", "Customer Food & Drink Order"),
        "items": sanitized_items,
        "subtotal": subtotal,
        "tax": tax,
        "total_price": total_price,
        "special_instructions": data.get("special_instructions", "None"),
        "source": data.get("source", "Mock Heuristic Engine")
    }


def parse_order_mock_fallback(raw_text: str) -> dict:
    """Rule-based smart fallback parser for testing without an active Groq API key."""
    text_lower = raw_text.lower()
    items = []

    # Heuristic item detection rules
    menu_catalog = [
        {"keywords": ["caramel macchiato", "macchiato"], "name": "Caramel Macchiato", "base_price": 5.25},
        {"keywords": ["americano"], "name": "Caffe Americano", "base_price": 4.00},
        {"keywords": ["latte"], "name": "Caffe Latte", "base_price": 4.75},
        {"keywords": ["cappuccino"], "name": "Cappuccino", "base_price": 4.50},
        {"keywords": ["mocha"], "name": "Caffe Mocha", "base_price": 5.00},
        {"keywords": ["espresso"], "name": "Espresso Shot", "base_price": 3.00},
        {"keywords": ["muffin", "blueberry muffin"], "name": "Blueberry Muffin", "base_price": 3.75},
        {"keywords": ["croissant"], "name": "Butter Croissant", "base_price": 3.50},
        {"keywords": ["bagel"], "name": "Everything Bagel", "base_price": 3.25},
        {"keywords": ["sandwich", "burger"], "name": "Breakfast Club Sandwich", "base_price": 7.50},
        {"keywords": ["fries", "curly fries"], "name": "Crispy French Fries", "base_price": 3.99}
    ]

    # Detect sizes
    size = "Standard"
    if "large" in text_lower or "venti" in text_lower:
        size = "Large"
    elif "medium" in text_lower or "grande" in text_lower:
        size = "Medium"
    elif "small" in text_lower or "tall" in text_lower:
        size = "Small"

    # Detect add-ons
    add_ons = []
    if "oat" in text_lower or "oat milk" in text_lower:
        add_ons.append("Oat Milk (+$0.75)")
    if "almond" in text_lower:
        add_ons.append("Almond Milk (+$0.75)")
    if "extra shot" in text_lower or "double shot" in text_lower:
        add_ons.append("Extra Espresso Shot (+$1.00)")
    if "iced" in text_lower or "ice" in text_lower:
        add_ons.append("Iced")
    if "warmed" in text_lower or "warm" in text_lower:
        add_ons.append("Warmed")
    if "dekaf" in text_lower or "decaf" in text_lower:
        add_ons.append("Decaf")
    if "less sugar" in text_lower or "no sugar" in text_lower:
        add_ons.append("No Sugar")

    # Match items
    matched = False
    for entry in menu_catalog:
        if any(k in text_lower for k in entry["keywords"]):
            matched = True
            price = entry["base_price"]
            if size == "Large":
                price += 0.75
            elif size == "Small":
                price -= 0.50
            if "Extra Espresso Shot (+$1.00)" in add_ons:
                price += 1.00
            
            items.append({
                "item": entry["name"],
                "size": size,
                "add_ons": add_ons,
                "price": round(price, 2)
            })

    if not matched:
        # Default generic item if no keyword matches catalog
        items.append({
            "item": raw_text.strip().capitalize()[:35] or "Custom Cafe Order",
            "size": size,
            "add_ons": add_ons if add_ons else ["Standard Preparation"],
            "price": 6.50
        })

    subtotal = sum(i["price"] for i in items)
    tax = round(subtotal * 0.08, 2)
    total_price = round(subtotal + tax, 2)

    # Special instructions heuristic
    instructions = "None"
    if "extra" in text_lower or "no" in text_lower or "please" in text_lower:
        instructions = "Custom customer request included in text."

    summary_items = ", ".join([f"{i['size']} {i['item']}" for i in items])

    return {
        "summary": summary_items,
        "items": items,
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "total_price": total_price,
        "special_instructions": instructions,
        "source": "Mock Heuristic Engine (Set GROQ_API_KEY in .env for live Groq LLM)"
    }
