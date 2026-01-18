"""
Saranda Cafe & Pizzeria - Knowledge Base

Complete menu and business data from official menu documents.
Used by prompts and function handlers for accurate information.

Source: Official Saranda Menu (January 2026)
"""

from typing import TypedDict, List, Dict, Any, Optional

# Type definitions for restaurant data
class MenuItem(TypedDict, total=False):
    name: str
    price: float
    description: str
    dietary: List[str]  # vg=vegetarian, v=vegan, vo=vegan option, GF=gluten free, GFO=gluten free option, n=contains nuts, spicy=🌶️
    recommended: str    # Optional recommendation notes
    spicy: bool


class RestaurantData(TypedDict):
    info: Dict[str, Any]
    menu: Dict[str, Dict[str, MenuItem]]
    popular_items: List[str]
    modifiers: Dict[str, float]
    policies: Dict[str, Any]


SARANDA_DATA: RestaurantData = {
    "info": {
        "name": "Saranda Cafe & Pizzeria",
        "short_name": "Saranda",
        "tagline": "Eat Different.",
        "phone": "(08) 6401 6397",
        "whatsapp": "+61 452 557 167",
        "address": "2/8 Mullingar Way, Landsdale WA 6065",
        "email": "sarandacafe@gmail.com",
        "instagram": "@saranda_cafe",
        "facebook": "facebook.com/sarandacafe",
        "hours": {
            "monday": "CLOSED",
            "tuesday": "4:30 PM - 9:00 PM",
            "wednesday": "4:30 PM - 9:00 PM",
            "thursday": "4:30 PM - 9:00 PM",
            "friday": "4:30 PM - 9:00 PM",
            "saturday": "11:30 AM - 2:00 PM, 4:30 PM - 9:00 PM",
            "sunday": "11:30 AM - 2:00 PM, 4:30 PM - 9:00 PM",
        },
        "peak_hours": "5:30 PM - 7:30 PM",
        "kitchen_cutoff": "5 minutes before close",
        "prep_time_normal": "15-20 minutes",
        "prep_time_busy": "up to 30 minutes",
        "capacity": 60,
        "max_group_size": 30,
        # Quality notes from menu
        "quality_notes": [
            "All items made of local produce",
            "RSPCA approved ingredients",
            "DOP certified ingredients",
            "Not a 100% gluten-free kitchen - advise staff of allergies",
        ],
        "service_fee": "10% service fee for dine-in",
    },
    "policies": {
        "pickup_only": True,  # Delivery via third-party apps only
        "pay_on_pickup": True,  # No phone payments
        "delivery_partners": ["Menulog", "Uber Eats"],  # From menu
        "cancellation_notice": "24 hours prior",
        "reservation_deposit": "Large groups only (negotiable)",
    },
    "menu": {
        # ==================== APPETIZERS ====================
        "appetizers": {
            "arancini": {
                "name": "Arancini Ball",
                "price": 16.00,
                "description": "Traditional breaded & fried risotto ball with chef's special filling, aioli",
                "dietary": ["vg"]
            },
            "burrata": {
                "name": "Burrata",
                "price": 10.00,
                "description": "Bed of cherry tomato, extra virgin olive oil",
                "dietary": ["v"]
            },
            "bruschetta": {
                "name": "Bruschetta",
                "price": 18.00,
                "description": "Tomato basil and red onion, balsamic glaze, grated grana padano",
                "dietary": ["vg"]
            },
            "calamari": {
                "name": "Calamari Fritti",
                "price": 19.00,
                "description": "Fried squid ring coated with golden flour, Italian herbs, lemon wedges, rocket salad, spicy mayo",
                "dietary": ["vo"]
            },
            "garlic_bread": {
                "name": "Garlic Bread",
                "price": 8.00,
                "description": "Fresh homemade crusty garlic bread",
                "dietary": ["vg"]
            },
            "rosemary_potatoes": {
                "name": "Rosemary Roasted Chat Potatoes",
                "price": 10.00,
                "dietary": ["v"]
            },
            "fries": {
                "name": "Fries",
                "price": 7.00,
                "dietary": ["v"]
            },
        },
        
        # ==================== LA PIZZA (Stone Baked) ====================
        # Gluten free pizza base add $3
        "pizza": {
            "pizza_bianca": {
                "name": "Pizza Bianca",
                "price": 17.00,
                "description": "Rosemary infused olive oil, confit garlic, traditional mozzarella, dried oregano",
                "dietary": ["vo"]
            },
            "margherita": {
                "name": "Margherita",
                "price": 18.00,
                "description": "Tomato sugo, traditional mozzarella, fresh basil, herbs",
                "dietary": ["vo"]
            },
            "buffalina": {
                "name": "Buffalina",
                "price": 23.00,
                "description": "Tomato sugo, fresh buffalo mozzarella, fresh basil, herbs"
            },
            "vegetarian": {
                "name": "Vegetarian",
                "price": 23.00,
                "description": "Tomato sugo, traditional mozzarella, roasted capsicum, fresh chilli, shallots, cherry tomato, mushroom",
                "dietary": ["vo"],
                "recommended": "opt. BBQ Base"
            },
            "pepperoni": {
                "name": "Signature Pepperoni",
                "price": 24.00,
                "description": "Tomato sugo, traditional mozzarella, cacciatore (Hunter) salami, calabria nduja",
                "spicy": True
            },
            "hawaiian": {
                "name": "Classic Hawaiian",
                "price": 23.00,
                "description": "Tomato sugo, traditional mozzarella, virginian ham, pineapple"
            },
            "cappricciosa": {
                "name": "Cappricciosa",
                "price": 24.00,
                "description": "Tomato sugo, traditional mozzarella, virginian sliced ham, mushroom, artichoke hearts",
                "recommended": "add olives"
            },
            "bbq_chicken": {
                "name": "BBQ Chicken",
                "price": 24.00,
                "description": "BBQ sugo, traditional mozzarella, roasted chicken, shallots, fresh chilli, roast capsicum, parsley"
            },
            "peri_peri_chicken": {
                "name": "Peri Peri Chicken",
                "price": 24.00,
                "description": "Tomato sugo, traditional mozzarella, roasted chicken, shallots, roast capsicum, traditional african peri sauce",
                "spicy": True
            },
            "napolitana": {
                "name": "Napolitana",
                "price": 24.00,
                "description": "Tomato sugo, traditional mozzarella, anchovies, capers, kalamata olives, confit garlic, cherry tomato"
            },
            "siciliana": {
                "name": "Siciliana",
                "price": 24.00,
                "description": "Tomato sugo, traditional mozzarella, cacciatore salami, casalingo salami, cherry tomato, kalamata olives, fresh chilli, mushroom",
                "spicy": True
            },
        },
        
        # ==================== SPECIALE (Gourmet Pizzas) ====================
        "pizza_speciale": {
            "shrimp_sensation": {
                "name": "Shrimp Sensation",
                "price": 26.00,
                "description": "Tomato sugo, traditional mozzarella, marinated prawns, shallots, cherry tomato, fresh chilli, endive"
            },
            "frutti_di_mare": {
                "name": "Frutti di Mare (Seafood)",
                "price": 26.00,
                "description": "Tomato sugo, traditional mozzarella, classic marinara mix, anchovies, fresh chilli, cherry tomato"
            },
            "saranda_speciale": {
                "name": "Saranda Speciale",
                "price": 26.00,
                "description": "Ask wait person for week special pizza"
            },
            "meat_lovers": {
                "name": "Meat Lovers",
                "price": 26.00,
                "description": "Tomato sugo, traditional mozzarella, virginian ham, casalingo salami, cacciatore, streaky bacon",
                "recommended": "opt. BBQ Base"
            },
            "supreme": {
                "name": "Supreme",
                "price": 27.00,
                "description": "Tomato sugo, traditional mozzarella, virginian ham, cacciatore, casalingo salami, mushroom, shallots, kalamata olives, roasted capsicum"
            },
            "prosciutto_burrata": {
                "name": "Prosciutto Burrata",
                "price": 25.00,
                "description": "Tomato sugo, traditional mozzarella, prosciutto di Parma, rocket, fresh burrata"
            },
            "sarda": {
                "name": "Sarda",
                "price": 25.00,
                "description": "Stracciatella cream sauce, traditional mozzarella, felino salami, calabria nduja, sage leaves"
            },
            "boscaiola": {
                "name": "Boscaiola",
                "price": 25.00,
                "description": "Stracciatella cream sauce, traditional mozzarella, fresh Italian sausages, mushroom, fresh chilli, shallots, parsley"
            },
            "pizza_broccolini": {
                "name": "Pizza Broccolini",
                "price": 25.00,
                "description": "Stracciatella cream sauce, traditional mozzarella, roasted broccolini, pumpkin, chat potato, hot honey",
                "dietary": ["vg"]
            },
            "sexy_truffle": {
                "name": "Sexy Truffle",
                "price": 27.00,
                "description": "Chef's special porcini mushroom cream sauce, traditional mozzarella, truffle infused endive, grated pecorino, fresh burrata",
                "dietary": ["vg"],
                "recommended": "add pancetta"
            },
            "romano": {
                "name": "Romano",
                "price": 25.00,
                "description": "Fresh cream sauce, traditional mozzarella, cured pancetta, free-range egg, parsley"
            },
        },
        
        # ==================== LA PASTA (Handcrafted) ====================
        # Gluten free pasta add $3
        "pasta": {
            "bolognese": {
                "name": "Ragu' alla Bolognese",
                "price": 24.00,
                "description": "Premium quality ground beef & lean pork mince, cured pancetta, marinara sauce",
                "dietary": ["GFO"]
            },
            "carbonara": {
                "name": "Fettuccine Carbonara",
                "price": 24.00,
                "description": "Streaky bacon, rich confit egg yolk, grana padano, cream",
                "dietary": ["GFO"]
            },
            "amatriciana": {
                "name": "Spaghetti all'amatriciana",
                "price": 24.00,
                "description": "Streaky bacon, premium vodka, cherry tomato, grana padano, marinara sauce",
                "dietary": ["GFO"]
            },
            "pink_lady": {
                "name": "Pink Lady",
                "price": 24.00,
                "description": "Chicken, streaky bacon, grana padano, marinara sauce, hint of cream",
                "dietary": ["GFO"]
            },
            "arrabiata": {
                "name": "Penne all'arrabiata",
                "price": 24.00,
                "description": "Smoked Italian sausages, cherry tomato, grana padano, chilli, parsley",
                "dietary": ["GFO"],
                "spicy": True
            },
            "seafood_marinara": {
                "name": "Seafood Marinara",
                "price": 26.00,
                "description": "Classic seafood marinara mix, cherry tomato, fresh chilli, marinara sauce",
                "dietary": ["GFO"]
            },
            "calabrese": {
                "name": "Calabrese Pasta",
                "price": 25.00,
                "description": "Calabrian salami, marinated prawns, baby spinach, cream sauce, grana padano, parsley",
                "dietary": ["GFO"]
            },
            "sausage_mushroom": {
                "name": "Sausage & Mushroom",
                "price": 24.00,
                "description": "Fresh Italian sausage, mushroom, asparagus, grana padano, cream sauce",
                "dietary": ["GFO", "vg", "vo"]
            },
            "creamy_chicken_mushroom": {
                "name": "Creamy Chicken Mushroom",
                "price": 24.00,
                "description": "Mushroom, chicken, grana padano, cream sauce",
                "dietary": ["GFO"],
                "recommended": "sundried tomato or chilli"
            },
            "truffle_ravioli": {
                "name": "Truffle Ravioli",
                "price": 26.00,
                "description": "Handcrafted ravioli filled with velvety ricotta, aromatic truffle, mushroom, grana padano, mushroom cream sauce",
                "dietary": ["vg"]
            },
            "beef_cheek_panzotti": {
                "name": "Beef Cheek Panzotti",
                "price": 26.00,
                "description": "Handcrafted panzotti filled with braised beef cheek, grana padano, decadent pink sauce, parsley"
            },
            "gnocchi_genovese": {
                "name": "Gnocchi Genovese",
                "price": 26.00,
                "description": "Handcrafted potato dumpling, basil pesto, grana padano, buffalo cheese, cream sauce, charred pine nuts",
                "dietary": ["n", "vo"]
            },
            "lasagne": {
                "name": "Homemade Lasagne",
                "price": 25.00,
                "description": "Traditional Bolognese mix served on fresh lasagne sheet with loads of cheese (grana padano, mozzarella), béchamel sauce. Served with fresh salad"
            },
        },
        
        # ==================== INSALATE (Salads) ====================
        "salads": {
            "caprese": {
                "name": "Caprese",
                "price": 13.00,
                "description": "Fresh buffalo mozzarella, tomatoes, sweet basil, seasoned with salt, EVOO, balsamic glaze"
            },
            "greek": {
                "name": "Greek",
                "price": 12.00,
                "description": "Cherry tomatoes, cucumber, capsicum, red onion, feta, olives, greek salad dressing"
            },
            "rucola": {
                "name": "Rucola",
                "price": 12.00,
                "description": "Rocket, pecorino romano, shaved pear, cherry tomato, honey"
            },
        },
        
        # ==================== SECONDI (Mains) ====================
        "mains": {
            "chilli_mussels": {
                "name": "Chilli Mussels",
                "price": 26.00,
                "description": "Fresh mussels slow cooked in marinara sauce and fresh chilli, served with fresh homemade bread",
                "dietary": ["GF"],
                "spicy": True
            },
            "creamy_garlic_prawns": {
                "name": "Creamy Garlic Prawns",
                "price": 26.00,
                "description": "Marinated prawns smothered in a creamy garlic sauce, butter, olive oil, lemon, reserve white wine and chopped fresh parsley, served with fresh homemade stone bake garlic bread"
            },
            "fish_of_the_day": {
                "name": "Fish of the Day",
                "price": 28.00,
                "description": "Ask wait person for week special"
            },
            "chicken_parmigiana": {
                "name": "Chicken Parmigiana",
                "price": 27.00,
                "description": "Crumbed butterfly chicken breast, rich marinara sauce & traditional mozzarella, grana padano, served with chips and salad"
            },
            "pollo_al_fungi": {
                "name": "Pollo al Fungi",
                "price": 27.00,
                "description": "Grilled marinated butterfly chicken breast fillet slow cooked in creamy mushroom sauce, served with rosemary roasted chat potato and boiled broccolini",
                "dietary": ["GF"]
            },
            "veal_parmigiana": {
                "name": "Veal Parmigiana",
                "price": 28.00,
                "description": "Veal tenderloin cutlet breaded in dried bread crumbs, rich marinara sauce, prosciutto di parma, mozzarella, grana padano finished in the oven. Served with spaghetti marinara"
            },
        },
        
        # ==================== IL DOLCE (Desserts) ====================
        "desserts": {
            "milk_cake": {
                "name": "Saranda's Milk Cake",
                "price": 10.00
            },
            "tiramisu": {
                "name": "Tiramisu Di Casa",
                "price": 12.00
            },
            "ice_cream_sundae": {
                "name": "Ice Cream Sundae",
                "price": 10.00
            },
        },
        
        # ==================== KIDS MEALS ====================
        "kids": {
            "chicken_chipees": {
                "name": "Chicken Chipees",
                "price": 10.00
            },
            "fish_chips": {
                "name": "Fish & Chips",
                "price": 12.00
            },
            "alfredo": {
                "name": "Alfredo",
                "price": 12.00,
                "dietary": ["vg"]
            },
            "napolitana": {
                "name": "Napolitana",
                "price": 12.00,
                "dietary": ["vg"]
            },
        },
        
        # ==================== DRINKS ====================
        "drinks": {
            "soft_drinks": {
                "name": "Soft Drinks",
                "price": 4.00,
                "description": "Coke, Coke Zero, Lemonade, Fanta, Solo lemon"
            },
            "spring_water": {
                "name": "Spring Water",
                "price": 3.00
            },
            "sparkling_water": {
                "name": "Sparkling Water",
                "price": 5.00
            },
            "strange_love": {
                "name": "Strange Love / Riviera",
                "price": 5.00
            },
            "coffee": {
                "name": "Cappuccino / Latte / Flat White",
                "price": 5.00
            },
            "affogato": {
                "name": "Affogato",
                "price": 6.00
            },
        },
    },
    
    # Owner-confirmed popular items
    "popular_items": [
        "Margherita",
        "Signature Pepperoni",
        "Fettuccine Carbonara",
        "Pink Lady",
    ],
    
    # Add-ons and modifiers with prices
    "modifiers": {
        # Pizza add-ons
        "gluten_free_pizza_base": 3.00,
        "gluten_free_pasta": 3.00,
        "crust_dipper": 2.00,  # Pesto mayo, Spicy mayo, Chimichurri
        # Topping add-ons
        "veg_topping": 2.00,
        "meat_topping": 3.00,
        "cheese_topping": 3.00,
        "prosciutto": 3.00,
        "seafood_topping": 4.00,
        "fresh_burrata": 6.00,
        # Common modifiers (free)
        "extra_chilli": 0.00,
        "no_onion": 0.00,
    },
    
    # Dietary legend from menu
    "dietary_legend": {
        "spicy": "🌶️ Spicy",
        "n": "Contains nuts",
        "v": "Vegan",
        "vo": "Vegan option available",
        "vg": "Vegetarian",
        "GF": "Gluten free",
        "GFO": "Gluten free option available",
    },
}


def get_menu_item_by_name(name: str) -> Optional[MenuItem]:
    """Find a menu item by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for category, items in SARANDA_DATA["menu"].items():
        for key, item in items.items():
            if name_lower in item["name"].lower() or name_lower in key:
                return item
    return None


def get_menu_category(category: str) -> Optional[Dict[str, MenuItem]]:
    """Get all items in a menu category."""
    return SARANDA_DATA["menu"].get(category)


def get_prep_time_estimate(is_busy: bool = False) -> str:
    """Get estimated prep time based on current load."""
    if is_busy:
        return SARANDA_DATA["info"]["prep_time_busy"]
    return SARANDA_DATA["info"]["prep_time_normal"]


def format_order_summary(items: List[Dict[str, Any]]) -> str:
    """Format order items into a readable summary for WhatsApp."""
    if not items:
        return "No items"
    
    lines = []
    for item in items:
        line = item.get("name", "Unknown")
        if item.get("modifiers"):
            mods = ", ".join(item["modifiers"])
            line += f" (+{mods})"
        if item.get("quantity", 1) > 1:
            line = f"{item['quantity']}x {line}"
        lines.append(line)
    
    return " | ".join(lines)


def is_restaurant_open(day: str, time_str: str = None) -> bool:
    """Check if restaurant is open on given day."""
    day_lower = day.lower()
    hours = SARANDA_DATA["info"]["hours"].get(day_lower, "CLOSED")
    return hours != "CLOSED"


def get_delivery_partners() -> List[str]:
    """Get list of delivery partners."""
    return SARANDA_DATA["policies"]["delivery_partners"]
