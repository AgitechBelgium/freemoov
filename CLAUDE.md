# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a custom **Odoo 17** module project for the client "freemoov" — an e-commerce website selling electric scooters (Belgium-based). The codebase consists of multiple Odoo addons developed or customized for this client.

## Local Development Environment

The v17 development environment runs via Docker:

```bash
# Start the Odoo 17 environment (port 8070)
docker compose -f docker-compose.v17.yml up

# Restart and force module update
docker compose -f docker-compose.v17.yml restart odoo17

# Update a specific module
docker exec freemoov-odoo17-test odoo -u website_freemoov --stop-after-init
```

- Odoo 17 runs at **http://localhost:8070**
- DB name: `freemoov-staging-27497775`
- `odoo-v17.conf` has `dev_mode = xml` enabled (XML views auto-reload without restart)

## Module Architecture

### Custom Modules

| Module | Purpose |
|--------|---------|
| `website_freemoov` | Main client module — shop customizations, product page, header/footer, stock display |
| `ust_common_features` | Third-party base module (Upstackers) — carousel, slider snippets, brand/tab models |
| `moov_reparation` | FSM repair sequence and task management |
| `mask_as_done_extends` | Extends `industry_fsm_stock` task "mark as done" |
| `pixel_meta` | Meta Pixel integration |
| `website_cookies_consent` | Cookie consent banner |
| `website_google_tag` | Google Tag Manager integration |
| `sky_signup_google_recaptcha` | Google reCAPTCHA on signup |

### `website_freemoov` Structure

- **`models/product.py`**: Extends `product.template` with custom fields (`pro_description`, `delivery_return`, `warranty_support`, `summary`, `is_dropship_product`, `tab_ids`) and overrides `_get_sales_prices` to force Belgian fiscal position (21% VAT). Also extends `product.public.category` with `brand_ids`, `category_description`, `category_bottom_content`.
- **`controllers/main.py`**: Two custom JSON routes — `/fetch_subcategories` (mobile category navigation) and `/shop/cart/popover` (cart popover HTML).
- **`views/`**: QWeb templates inheriting Odoo core views via `xpath`. Several views are explicitly `active="False"` because their parent view structure changed in Odoo 17 (documented inline).
- **`static/src/js/common.js`**: jQuery-based frontend JS using native `fetch()` for AJAX (not Odoo's legacy `jsonrpc`/`rpc` imports). Uses `/** @odoo-module **/` header.
- **`static/src/js/variant.js`**: Product variant handling, also uses native `fetch()`.
- **`static/src/xml/stock_availability.xml`**: OWL/QWeb component inheriting `website_sale_stock.product_availability`.

## Key Conventions

### JavaScript
- All JS files must start with `/** @odoo-module **/`
- Use native `fetch()` with JSON-RPC format for AJAX calls — do **not** import Odoo's `jsonrpc` or `@web/core/network/rpc`
- jQuery is available globally on the frontend

### XML Views
- When a parent view structure changes in Odoo 17, disable the override with `<field name="active" eval="False"/>` and add a comment explaining why, rather than trying to patch a broken xpath
- Use `position="replace"` or `position="after"` with xpath targeting specific elements

### Python Models
- Follow standard Odoo inheritance: `_inherit = "model.name"`
- Fiscal position override in `_get_sales_prices` is intentional — forces Belgian VAT for all website visitors regardless of detected country

## Migration Context

This project is in the process of migrating from **Odoo 16 (production)** to **Odoo 17 (staging → production)**. The staging environment at `freemoov-staging-27497775.dev.odoo.com` is the v17 target. Odoo.sh staging environments are automatically neutralized (emails, payments, crons disabled) — this is expected behavior.

Migration scripts are in `scripts/` (excluded from git):
```bash
python scripts/sync_prod_to_staging.py --model product.template --since-id 2377
```
