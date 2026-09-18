import threading
from datetime import datetime

class OrderStore:
    """Thread-safe in-memory order queue for staff kitchen view."""
    def __init__(self):
        self._orders = []
        self._lock = threading.Lock()
        self._counter = 100

        # Seed with a sample order for immediate visual demo
        self.add_order(
            customer_name="Demo Customer",
            raw_text="1 Large Iced Oat Caramel Macchiato with extra espresso shot and 1 Warmed Blueberry Muffin",
            parsed_data={
                "summary": "Large Iced Oat Milk Caramel Macchiato (+extra shot), Warmed Blueberry Muffin",
                "customer_name": "Demo Customer",
                "items": [
                    {
                        "item": "Iced Caramel Macchiato",
                        "size": "Large",
                        "add_ons": ["Oat Milk", "Extra Espresso Shot"],
                        "price": 5.75
                    },
                    {
                        "item": "Blueberry Muffin",
                        "size": "Standard",
                        "add_ons": ["Warmed"],
                        "price": 3.50
                    }
                ],
                "subtotal": 9.25,
                "tax": 0.74,
                "total_price": 9.99,
                "special_instructions": "Make it extra hot if possible for the muffin."
            },
            status="Pending"
        )

    def add_order(self, customer_name: str, raw_text: str, parsed_data: dict, status: str = "Pending") -> dict:
        with self._lock:
            self._counter += 1
            order_id = f"ORD-{self._counter}"
            now = datetime.now()
            
            order = {
                "id": order_id,
                "customer_name": customer_name or "Guest",
                "raw_text": raw_text,
                "parsed_data": parsed_data,
                "status": status,  # Pending, Preparing, Ready, Completed
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "time_display": now.strftime("%I:%M %p")
            }
            # Add to top of queue (newest first)
            self._orders.insert(0, order)
            return order

    def get_all_orders(self, status_filter: str = None) -> list:
        with self._lock:
            if status_filter and status_filter.lower() != "all":
                return [o for o in self._orders if o["status"].lower() == status_filter.lower()]
            return list(self._orders)

    def get_order_by_id(self, order_id: str) -> dict:
        with self._lock:
            for o in self._orders:
                if o["id"] == order_id:
                    return o
            return None

    def update_order_status(self, order_id: str, new_status: str) -> dict:
        with self._lock:
            valid_statuses = ["Pending", "Preparing", "Ready", "Completed"]
            if new_status not in valid_statuses:
                raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")
            
            for o in self._orders:
                if o["id"] == order_id:
                    o["status"] = new_status
                    o["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    return o
            return None

    def get_summary_counts(self) -> dict:
        with self._lock:
            counts = {"Pending": 0, "Preparing": 0, "Ready": 0, "Completed": 0, "Total": len(self._orders)}
            for o in self._orders:
                status = o.get("status", "Pending")
                if status in counts:
                    counts[status] += 1
            return counts


# Global singleton instance
order_store = OrderStore()
