#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    action = payload.get("action")
    if action not in ("insert", "delete", "list"):
        print(json.dumps({"success": False, "error": "Invalid action"}))
        sys.exit(1)
    from google.shopping import merchant_products_v1
    from google.shopping.merchant_products_v1 import Availability, Condition
    from google.shopping.type import Price
    merchant_id = str(payload["merchant_id"])
    data_source_id = str(payload["data_source_id"])
    credentials_json = payload["credentials_json"]
    parent = "accounts/%s" % merchant_id
    data_source = "accounts/%s/dataSources/%s" % (merchant_id, data_source_id)

    if action == "list":
        try:
            list_client = merchant_products_v1.ProductsServiceClient.from_service_account_info(credentials_json)
            request = merchant_products_v1.ListProductsRequest(parent=parent, page_size=250)
            all_products = []
            page_result = list_client.list_products(request=request)
            for product in page_result:
                attrs = getattr(product, "product_attributes", None)
                price = getattr(attrs, "price", None) if attrs else None
                price_micros = getattr(price, "amount_micros", 0) if price else 0
                price_currency = getattr(price, "currency_code", "EUR") if price else "EUR"
                all_products.append({
                    "name": getattr(product, "name", ""),
                    "offer_id": getattr(product, "offer_id", ""),
                    "content_language": getattr(product, "content_language", ""),
                    "feed_label": getattr(product, "feed_label", ""),
                    "title": getattr(attrs, "title", "") if attrs else "",
                    "price_micros": price_micros,
                    "currency_code": price_currency,
                    "availability": str(getattr(attrs, "availability", "")) if attrs else "",
                    "link": getattr(attrs, "link", "") if attrs else "",
                })
            print(json.dumps({"success": True, "products": all_products, "count": len(all_products)}))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return

    client = merchant_products_v1.ProductInputsServiceClient.from_service_account_info(credentials_json)
    if action == "delete":
        offer_id = payload["offer_id"]
        content_language = payload.get("content_language", "fr")
        feed_label = payload.get("feed_label", "BE")
        name = "accounts/%s/productInputs/%s~%s~%s" % (merchant_id, content_language, feed_label, offer_id)
        try:
            request = merchant_products_v1.DeleteProductInputRequest(name=name, data_source=data_source)
            client.delete_product_input(request=request)
            print(json.dumps({"success": True}))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    product_data = payload["product_data"]
    attrs = merchant_products_v1.ProductAttributes()
    attrs.title = (product_data.get("title") or "")[:150]
    attrs.description = (product_data.get("description") or "")[:5000]
    attrs.link = product_data.get("link") or ""
    attrs.image_link = product_data.get("image_link") or ""
    if product_data.get("additional_image_links"):
        attrs.additional_image_links.extend(product_data["additional_image_links"][:10])
    availability = product_data.get("availability", "IN_STOCK").upper()
    attrs.availability = getattr(Availability, availability, Availability.IN_STOCK)
    condition = (product_data.get("condition") or "new").lower()
    if condition == "used":
        attrs.condition = Condition.USED
    elif condition == "refurbished":
        attrs.condition = Condition.REFURBISHED
    else:
        attrs.condition = Condition.NEW
    price = Price()
    price.amount_micros = int(product_data.get("price_micros", 0))
    price.currency_code = product_data.get("currency_code", "EUR")
    attrs.price = price
    if product_data.get("google_product_category"):
        attrs.google_product_category = product_data["google_product_category"][:750]
    if product_data.get("gtin"):
        attrs.gtins.append(str(product_data["gtin"]))
    if product_data.get("mpn"):
        attrs.mpn = product_data["mpn"][:70]
    if product_data.get("brand"):
        attrs.brand = product_data["brand"][:70]
    if product_data.get("shipping_weight_value") and product_data["shipping_weight_value"] > 0:
        from google.shopping.merchant_products_v1 import ShippingWeight
        sw = ShippingWeight()
        sw.value = float(product_data["shipping_weight_value"])
        sw.unit = product_data.get("shipping_weight_unit", "kg")
        attrs.shipping_weight = sw
    product_input = merchant_products_v1.ProductInput()
    product_input.offer_id = str(product_data.get("offer_id", ""))[:50]
    product_input.content_language = product_data.get("content_language", "fr")
    product_input.feed_label = product_data.get("feed_label", "BE")
    product_input.product_attributes = attrs
    try:
        request = merchant_products_v1.InsertProductInputRequest(parent=parent, product_input=product_input, data_source=data_source)
        response = client.insert_product_input(request=request)
        gmc_id = getattr(response, "name", None) or str(response)
        print(json.dumps({"success": True, "gmc_product_id": gmc_id}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    main()
