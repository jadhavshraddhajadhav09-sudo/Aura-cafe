import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from groq_service import parse_order_with_groq
from order_store import order_store

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-shadu-app")


@app.route("/")
def customer_view():
    """Customer order input & parsing page."""
    api_key_configured = bool(os.getenv("GROQ_API_KEY", "").strip())
    return render_template("customer.html", api_key_configured=api_key_configured)


@app.route("/staff")
def staff_view():
    """Staff Kitchen Display & Queue management view."""
    return render_template("staff.html")


@app.route("/api/parse-order", methods=["POST"])
def api_parse_order():
    """Endpoint: Parses freeform customer order text into structured JSON via Groq API."""
    data = request.get_json() or {}
    raw_text = data.get("raw_text", "").strip()

    if not raw_text:
        return jsonify({
            "success": False,
            "error": "Please type or dictate your order before submitting."
        }), 400

    try:
        parsed_result = parse_order_with_groq(raw_text)
        return jsonify({
            "success": True,
            "raw_text": raw_text,
            "parsed": parsed_result
        })
    except Exception as e:
        app.logger.error(f"Error parsing order: {e}")
        return jsonify({
            "success": False,
            "error": f"Failed to process order: {str(e)}"
        }), 500


@app.route("/api/confirm-order", methods=["POST"])
def api_confirm_order():
    """Endpoint: Confirms a parsed order and places it into the staff queue."""
    data = request.get_json() or {}
    customer_name = data.get("customer_name", "Guest Customer").strip()
    raw_text = data.get("raw_text", "").strip()
    parsed_data = data.get("parsed_data", {})

    if not parsed_data or not parsed_data.get("items"):
        return jsonify({
            "success": False,
            "error": "Invalid order data provided for confirmation."
        }), 400

    order = order_store.add_order(
        customer_name=customer_name or "Guest Customer",
        raw_text=raw_text,
        parsed_data=parsed_data,
        status="Pending"
    )

    return jsonify({
        "success": True,
        "message": "Order successfully submitted to kitchen queue!",
        "order": order
    })


@app.route("/api/orders", methods=["GET"])
def api_get_orders():
    """Endpoint: Fetches active orders for staff display with filter support."""
    status_filter = request.args.get("status", "all").strip()
    orders = order_store.get_all_orders(status_filter=status_filter)
    counts = order_store.get_summary_counts()
    
    return jsonify({
        "success": True,
        "orders": orders,
        "counts": counts,
        "filter": status_filter
    })


@app.route("/api/orders/<order_id>/status", methods=["PATCH"])
def api_update_order_status(order_id):
    """Endpoint: Updates order status (Pending -> Preparing -> Ready -> Completed)."""
    data = request.get_json() or {}
    new_status = data.get("status", "").strip()

    if not new_status:
        return jsonify({"success": False, "error": "New status is required."}), 400

    try:
        updated_order = order_store.update_order_status(order_id, new_status)
        if not updated_order:
            return jsonify({"success": False, "error": "Order not found."}), 404
        
        return jsonify({
            "success": True,
            "message": f"Order {order_id} status updated to '{new_status}'",
            "order": updated_order
        })
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400


@app.route("/api/status", methods=["GET"])
def api_health():
    """Health check endpoint."""
    return jsonify({
        "status": "online",
        "groq_key_set": bool(os.getenv("GROQ_API_KEY", "").strip())
    })


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"\n[SERVER] Running on http://127.0.0.1:{port}")
    print(f"[*] Customer Order View: http://127.0.0.1:{port}/")
    print(f"[*] Staff Kitchen View: http://127.0.0.1:{port}/staff\n")
    app.run(host="0.0.0.0", port=port, debug=True)
