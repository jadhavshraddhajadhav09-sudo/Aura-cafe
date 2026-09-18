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


/**
 * Aura AI Coffee Shop Assistant Interface Logic
 */

let menuCatalog = null;
let currentParsedData = null;
let activeCustomizeItem = null;

const PRESETS = {
    1: "Hi Aura! I'd like 1 large iced caramel macchiato with extra oat milk and extra shot, plus 2 warm blueberry muffins!",
    2: "Can I get 1 medium caffe latte with almond milk, plus 1 breakfast club sandwich (extra hot)?",
    3: "I'd like 1 double shot caffe americano (hot) and 1 fresh butter croissant toasted."
};

document.addEventListener('DOMContentLoaded', () => {
    loadMenu();
});

async function loadMenu() {
    try {
        const response = await fetch('/api/menu');
        const data = await response.json();
        if (data.success) {
            menuCatalog = data.menu;
            renderMenuGrid('coffees', 'coffee-grid');
            renderMenuGrid('snacks', 'snack-grid');
        }
    } catch (err) {
        console.error("Failed to load menu:", err);
    }
}

function renderMenuGrid(categoryKey, containerId) {
    const container = document.getElementById(containerId);
    if (!container || !menuCatalog || !menuCatalog[categoryKey]) return;

    const items = menuCatalog[categoryKey];
    container.innerHTML = '';

    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'menu-item-card';

        const popularBadge = item.popular ? `<span class="popular-badge"><i class="fa-solid fa-fire text-amber"></i> Popular</span>` : '';
        
        card.innerHTML = `
            <div class="menu-card-header">
                <div class="menu-card-icon">
                    <i class="fa-solid ${item.icon}"></i>
                </div>
                ${popularBadge}
            </div>
            <div class="menu-card-body">
                <h4 class="menu-item-title">${escapeHtml(item.name)}</h4>
                <p class="menu-item-desc">${escapeHtml(item.description)}</p>
                <div class="menu-card-footer">
                    <span class="menu-item-price">$${parseFloat(item.price).toFixed(2)}</span>
                    <button type="button" class="btn btn-sm btn-primary" onclick="openCustomizeModal('${categoryKey}', '${item.id}')">
                        <i class="fa-solid fa-sliders"></i> Customize
                    </button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.style.display = 'none');

    const selectedBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
    if (selectedBtn) selectedBtn.classList.add('active');

    const pane = document.getElementById(`tab-${tabId}`);
    if (pane) pane.style.display = 'block';
}

function openCustomizeModal(categoryKey, itemId) {
    if (!menuCatalog || !menuCatalog[categoryKey]) return;
    const item = menuCatalog[categoryKey].find(i => i.id === itemId);
    if (!item) return;

    activeCustomizeItem = item;
    const modalTitle = document.getElementById('custom-modal-title');
    const modalBody = document.getElementById('custom-modal-body');

    modalTitle.innerHTML = `<i class="fa-solid ${item.icon} text-amber"></i> Customize ${escapeHtml(item.name)}`;

    let html = `
        <div class="custom-item-summary">
            <p class="text-muted" style="font-size: 0.9rem; margin-bottom: 1rem;">${escapeHtml(item.description)}</p>
        </div>
        <form id="custom-item-form">
    `;

    if (item.category === "Coffee") {
        html += `
            <div class="form-group">
                <label><i class="fa-solid fa-expand text-cyan"></i> Select Size:</label>
                <div class="radio-group-horizontal">
                    <label class="radio-chip"><input type="radio" name="c_size" value="Small" /> Small</label>
                    <label class="radio-chip"><input type="radio" name="c_size" value="Medium" checked /> Medium ($${item.price.toFixed(2)})</label>
                    <label class="radio-chip"><input type="radio" name="c_size" value="Large" /> Large (+$0.75)</label>
                </div>
            </div>
            <div class="form-group">
                <label><i class="fa-solid fa-cow text-purple"></i> Milk Choice:</label>
                <select id="c_milk" class="custom-select">
                    <option value="Whole Milk">Whole Milk (Standard)</option>
                    <option value="Oat Milk">Oat Milk (+$0.75)</option>
                    <option value="Almond Milk">Almond Milk (+$0.75)</option>
                    <option value="Skim Milk">Skim Milk</option>
                </select>
            </div>
            <div class="form-group">
                <label><i class="fa-solid fa-temperature-half text-amber"></i> Temperature:</label>
                <div class="radio-group-horizontal">
                    <label class="radio-chip"><input type="radio" name="c_temp" value="Hot" checked /> Hot ☕</label>
                    <label class="radio-chip"><input type="radio" name="c_temp" value="Iced" /> Iced 🧊</label>
                </div>
            </div>
            <div class="form-group">
                <label><i class="fa-solid fa-bolt text-green"></i> Espresso Shot:</label>
                <select id="c_shot" class="custom-select">
                    <option value="Single Shot">Standard Shot</option>
                    <option value="Extra Espresso Shot">Extra Espresso Shot (+$1.00)</option>
                    <option value="Decaf">Decaf Espresso</option>
                </select>
            </div>
        `;
    } else {
        html += `
            <div class="form-group">
                <label><i class="fa-solid fa-fire-burner text-amber"></i> Preparation Preference:</label>
                <div class="radio-group-horizontal">
                    <label class="radio-chip"><input type="radio" name="s_prep" value="Warmed" checked /> Warmed Up 🔥</label>
                    <label class="radio-chip"><input type="radio" name="s_prep" value="Room Temp" /> Room Temperature</label>
                </div>
            </div>
        `;
    }

    html += `
        <div class="form-group">
            <label><i class="fa-solid fa-hashtag text-cyan"></i> Quantity:</label>
            <input type="number" id="c_qty" value="1" min="1" max="10" style="max-width: 120px;" />
        </div>
    </form>`;

    modalBody.innerHTML = html;
    document.getElementById('customize-modal').style.display = 'flex';
}

function closeCustomizeModal() {
    document.getElementById('customize-modal').style.display = 'none';
    activeCustomizeItem = null;
}

function confirmCustomizeItem() {
    if (!activeCustomizeItem) return;

    const qty = parseInt(document.getElementById('c_qty').value) || 1;
    let desc = `${qty} `;

    if (activeCustomizeItem.category === "Coffee") {
        const size = document.querySelector('input[name="c_size"]:checked')?.value || "Medium";
        const temp = document.querySelector('input[name="c_temp"]:checked')?.value || "Hot";
        const milk = document.getElementById('c_milk').value;
        const shot = document.getElementById('c_shot').value;

        desc += `${size} ${temp} ${activeCustomizeItem.name}`;
        let extras = [];
        if (milk !== "Whole Milk") extras.push(milk);
        if (shot !== "Single Shot") extras.push(shot);
        if (extras.length > 0) desc += ` with ${extras.join(' and ')}`;
    } else {
        const prep = document.querySelector('input[name="s_prep"]:checked')?.value || "Warmed";
        desc += `${prep} ${activeCustomizeItem.name}`;
    }

    // Append to existing text input or parse directly
    const input = document.getElementById('raw-order-input');
    if (input.value.trim().length > 0) {
        input.value += `, plus ${desc}`;
    } else {
        input.value = desc;
    }

    closeCustomizeModal();
    showToast(`Added ${activeCustomizeItem.name} to order builder!`, "success");

    // Automatically submit to calculate bill
    triggerParseOrder();
}

function applyPreset(id) {
    const text = PRESETS[id] || "";
    const input = document.getElementById('raw-order-input');
    input.value = text;
    showToast("Preset combo loaded!", "info");
    triggerParseOrder();
}

function clearInput() {
    document.getElementById('raw-order-input').value = '';
    resetReviewCard();
}

function resetReviewCard() {
    currentParsedData = null;
    document.getElementById('empty-state').style.display = 'block';
    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('parsed-content').style.display = 'none';
}

function triggerParseOrder() {
    const form = document.getElementById('order-form');
    if (form) {
        handleParseOrder(new Event('submit'));
    }
}

async function handleParseOrder(e) {
    if (e && e.preventDefault) e.preventDefault();
    const rawText = document.getElementById('raw-order-input').value.trim();
    if (!rawText) {
        showToast("Please select items or describe your order first.", "error");
        return;
    }

    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('parsed-content').style.display = 'none';
    document.getElementById('loading-state').style.display = 'block';
    
    const btnParse = document.getElementById('btn-parse');
    if (btnParse) {
        btnParse.disabled = true;
        btnParse.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Calculating Bill...`;
    }

    try {
        const response = await fetch('/api/parse-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_text: rawText })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || "Failed to parse order");
        }

        currentParsedData = data.parsed;
        renderParsedOrder(data.parsed);
        showToast("Aura calculated your bill & prep time!", "success");

    } catch (err) {
        console.error(err);
        showToast(err.message, "error");
        document.getElementById('loading-state').style.display = 'none';
        document.getElementById('empty-state').style.display = 'block';
    } finally {
        if (btnParse) {
            btnParse.disabled = false;
            btnParse.innerHTML = `<i class="fa-solid fa-sparkles"></i> Aura, Calculate My Bill!`;
        }
    }
}

function renderParsedOrder(parsed) {
    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('parsed-content').style.display = 'block';

    // AI Greeting Message
    if (parsed.friendly_message) {
        document.getElementById('ai-greeting-text').textContent = parsed.friendly_message;
    }

    // Summary, Source & Prep Time
    document.getElementById('order-summary-title').textContent = parsed.summary || "Coffee & Snack Order";
    document.getElementById('order-source-badge').textContent = parsed.source || "Aura AI Barista";
    document.getElementById('prep-time-val').textContent = parsed.prep_time_display || "4 - 6 mins";

    // Items list
    const itemsContainer = document.getElementById('items-list');
    itemsContainer.innerHTML = '';

    (parsed.items || []).forEach(item => {
        const card = document.createElement('div');
        card.className = 'order-item-card';

        const addOnsHtml = (item.add_ons || []).map(addon => 
            `<span class="addon-pill">+ ${escapeHtml(addon)}</span>`
        ).join('');

        const categoryIcon = item.category === "Snack" ? 'fa-cookie-bite' : 'fa-mug-hot';

        card.innerHTML = `
            <div class="item-main">
                <div class="item-title">
                    <i class="fa-solid ${categoryIcon} text-amber"></i>
                    <span>${escapeHtml(item.item)}</span>
                    <span class="item-size-badge">${escapeHtml(item.size || 'Standard')}</span>
                </div>
                <div class="item-addons">
                    ${addOnsHtml || '<span style="font-size:0.75rem; color:#64748b;">Standard Preparation</span>'}
                </div>
            </div>
            <div class="item-price">$${parseFloat(item.price || 0).toFixed(2)}</div>
        `;
        itemsContainer.appendChild(card);
    });

    // Special Instructions
    const instrBox = document.getElementById('instructions-container');
    const instrText = document.getElementById('special-instructions-text');
    if (parsed.special_instructions && parsed.special_instructions !== "None") {
        instrText.textContent = parsed.special_instructions;
        instrBox.style.display = 'block';
    } else {
        instrBox.style.display = 'none';
    }

    // Pricing
    document.getElementById('subtotal-val').textContent = `$${parseFloat(parsed.subtotal || 0).toFixed(2)}`;
    document.getElementById('tax-val').textContent = `$${parseFloat(parsed.tax || 0).toFixed(2)}`;
    document.getElementById('total-val').textContent = `$${parseFloat(parsed.total_price || 0).toFixed(2)}`;
}

async function handleConfirmOrder() {
    if (!currentParsedData) return;

    const customerName = document.getElementById('customer-name-input').value.trim() || "Guest Customer";
    const rawText = document.getElementById('raw-order-input').value.trim();
    const btnConfirm = document.getElementById('btn-confirm');

    btnConfirm.disabled = true;
    btnConfirm.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Submitting to Kitchen...`;

    try {
        const response = await fetch('/api/confirm-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                customer_name: customerName,
                raw_text: rawText,
                parsed_data: currentParsedData
            })
        });

        const res = await response.json();

        if (!res.success) {
            throw new Error(res.error || "Failed to confirm order");
        }

        // Show success modal with Order ID & Preparation Time
        document.getElementById('placed-order-id').textContent = res.order.id;
        document.getElementById('placed-prep-time').textContent = res.order.parsed_data.prep_time_display || "4 - 6 minutes";
        document.getElementById('active-order-modal').style.display = 'flex';
        
        showToast(`Order ${res.order.id} confirmed! Est. Prep Time: ${res.order.parsed_data.prep_time_display}`, "success");
        
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btnConfirm.disabled = false;
        btnConfirm.innerHTML = `<i class="fa-solid fa-circle-check"></i> Confirm Order & Get Order #`;
    }
}

function closeOrderModal() {
    document.getElementById('active-order-modal').style.display = 'none';
    clearInput();
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
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
