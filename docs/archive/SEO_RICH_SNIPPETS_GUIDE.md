# Google Rich Snippets — Product Stars Implementation Guide

How to get star ratings, price, stock status, shipping and return info displayed under your Google search results using JSON-LD structured data.

Based on reverse-engineering sites that successfully display rich snippets (Weebot, Alteravenir) and Google Search Console validation.

---

## What Google displays

When properly implemented, Google shows under your search result:

```
Trottinette Electrique Dualtron Togo Limited | Freemoov
Description du produit...
629,00 € · En stock · 4,8 ★★★★★ (350) · Livraison gratuite · Retours sous 14 jour(s)
```

Each element maps to a specific JSON-LD property.

---

## Minimal JSON-LD that triggers stars

Google requires a `Product` schema with **at least** `offers` + `aggregateRating` + `review`. In practice, having all three is what reliably triggers the star display.

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Product Name | Brand",
  "description": "Product description",
  "url": "https://example.com/product-url",
  "image": ["https://example.com/product-image.jpg"],
  "sku": "SKU123",
  "brand": {
    "@type": "Brand",
    "name": "Brand Name"
  },
  "offers": {
    "@type": "Offer",
    "url": "https://example.com/product-url",
    "priceCurrency": "EUR",
    "price": "629.00",
    "priceValidUntil": "2026-09-01",
    "availability": "https://schema.org/InStock",
    "itemCondition": "https://schema.org/NewCondition"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "reviewCount": 350,
    "bestRating": 5,
    "worstRating": 1
  },
  "review": [
    {
      "@type": "Review",
      "author": {"@type": "Person", "name": "John Doe"},
      "datePublished": "2026-02-10",
      "reviewBody": "Great product, fast delivery.",
      "reviewRating": {
        "@type": "Rating",
        "ratingValue": 5,
        "bestRating": 5
      }
    }
  ]
}
</script>
```

### What each property triggers in Google SERP

| JSON-LD property | Google display |
|---|---|
| `offers.price` + `offers.priceCurrency` | **629,00 EUR** |
| `offers.availability` = `InStock` | **En stock** (green dot) |
| `aggregateRating.ratingValue` + `reviewCount` | **4,8 ★★★★★ (350)** |
| `offers.shippingDetails` with rate 0 | **Livraison gratuite** |
| `offers.hasMerchantReturnPolicy.merchantReturnDays` | **Retours sous 14 jour(s)** |

---

## Field-by-field breakdown

### 1. Product base (required)

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Product Name",
  "description": "Sales description or meta description",
  "url": "https://www.example.com/shop/product-slug",
  "image": ["https://www.example.com/product-image.jpg"],
  "sku": "REF-123",
  "brand": {
    "@type": "Brand",
    "name": "Brand Name"
  }
}
```

- `name`: product title, ideally matching `<title>` tag
- `sku`: internal reference or supplier code. If unavailable, use empty string
- `gtin13`: EAN barcode if available (strongly recommended for Google Shopping)
- `image`: array of image URLs, at least 1

### 2. Offers (triggers price + stock + shipping + returns)

```json
"offers": {
  "@type": "Offer",
  "url": "https://www.example.com/shop/product-slug",
  "priceCurrency": "EUR",
  "price": "629.00",
  "priceValidUntil": "2026-09-01",
  "availability": "https://schema.org/InStock",
  "itemCondition": "https://schema.org/NewCondition",
  "seller": {
    "@type": "Organization",
    "name": "Store Name"
  },
  "shippingDetails": [...],
  "hasMerchantReturnPolicy": {...}
}
```

- `price`: tax-included price as string with 2 decimals
- `priceValidUntil`: set to ~90 days from now (ISO date), Google uses this to validate freshness
- `availability`: `InStock`, `OutOfStock`, `PreOrder` — use schema.org full URLs
- `itemCondition`: `NewCondition`, `UsedCondition`, `RefurbishedCondition`

### 3. Shipping details (triggers "Livraison gratuite")

```json
"shippingDetails": [
  {
    "@type": "OfferShippingDetails",
    "shippingDestination": {
      "@type": "DefinedRegion",
      "addressCountry": "BE"
    },
    "shippingRate": {
      "@type": "MonetaryAmount",
      "value": 0.00,
      "currency": "EUR"
    },
    "deliveryTime": {
      "@type": "ShippingDeliveryTime",
      "handlingTime": {
        "@type": "QuantitativeValue",
        "minValue": 0,
        "maxValue": 2,
        "unitCode": "DAY"
      },
      "transitTime": {
        "@type": "QuantitativeValue",
        "minValue": 2,
        "maxValue": 5,
        "unitCode": "DAY"
      }
    }
  }
]
```

- One entry per country you ship to
- `value: 0.00` triggers "Livraison gratuite" in Google
- `unitCode`: always `"DAY"`

### 4. Return policy (triggers "Retours sous X jour(s)")

```json
"hasMerchantReturnPolicy": {
  "@type": "MerchantReturnPolicy",
  "applicableCountry": ["BE", "FR", "LU", "NL"],
  "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
  "merchantReturnDays": 14,
  "returnMethod": [
    "https://schema.org/ReturnByMail",
    "https://schema.org/ReturnInStore"
  ],
  "returnFees": "https://schema.org/ReturnFeesCustomerResponsibility"
}
```

### 5. AggregateRating (triggers stars + count)

```json
"aggregateRating": {
  "@type": "AggregateRating",
  "ratingValue": "4.8",
  "reviewCount": 350,
  "bestRating": 5,
  "worstRating": 1
}
```

- `ratingValue`: your average rating (from Google Business, Trustpilot, or per-product)
- `reviewCount`: total number of reviews
- `bestRating` / `worstRating`: scale boundaries (always 5/1 for stars)

### 6. Review (required to reliably trigger star display)

This is the key piece most implementations miss. Google is much more likely to show stars when you provide at least one concrete `review` alongside `aggregateRating`.

```json
"review": [
  {
    "@type": "Review",
    "author": {"@type": "Person", "name": "Real Person Name"},
    "datePublished": "2026-02-10",
    "reviewBody": "Actual review text from a real customer.",
    "reviewRating": {
      "@type": "Rating",
      "ratingValue": 5,
      "bestRating": 5
    }
  }
]
```

- Use **real reviews** from your Google Business profile, Trustpilot, or on-site reviews
- `datePublished`: ISO date, should be recent (within the last year)
- `reviewBody`: actual review text, not fabricated
- Can be an array of multiple reviews (3 is a good number)

---

## Approaches used in the wild

### Approach A: Per-product reviews (Weebot / Judge.me)

- Uses a third-party review collection tool (Judge.me, Avis Verifies, Trustpilot)
- Sends post-purchase emails to collect per-product reviews
- JSON-LD is generated dynamically from real per-product review data
- Most legitimate, highest credibility
- Requires ongoing review collection effort

### Approach B: Store-wide reviews on Product schema (Freemoov / Alteravenir)

- Uses Google Business reviews (store-level, not per-product)
- Hardcodes `aggregateRating` + a few real `review` entries in JSON-LD
- Applied to all product pages as a fallback
- Borderline but widely used and accepted by Google
- Works immediately, no review collection infrastructure needed
- Should transition to per-product reviews over time

### Approach C: Widget + hardcoded JSON-LD (Alteravenir)

- Embeds Elfsight Google Reviews widget (visual carousel of Google reviews)
- Separately injects a hardcoded JSON-LD `Product` schema with `aggregateRating` + `review`
- The widget provides visual proof to Google that reviews exist on the page
- The JSON-LD provides the structured data Google needs for rich snippets

---

## Validation

### Google Rich Results Test

Test your pages at: https://search.google.com/test/rich-results

Should show: "Product — Eligible for rich results"

### Google Search Console

Monitor at: Search Console > Enhancements > Product snippets

Common errors:
- "Missing field offers" — add the `offers` block
- "Missing field review or aggregateRating" — add both
- "Invalid value in field availability" — use full schema.org URLs

### Key validation points

- `@type` must be `Product` (not `Organization`, not `LocalBusiness`)
- `offers` must have `price`, `priceCurrency`, `availability`
- `aggregateRating` must have `ratingValue`, `reviewCount`
- `review` must have `author`, `reviewRating`, `datePublished`, `reviewBody`
- All URLs must be absolute (https://...)
- `price` must be a string or number, not empty

---

## Timeline expectations

After deploying valid structured data:
1. **Day 1-3**: Google Rich Results Test validates immediately
2. **Week 1-2**: Google recrawls your pages (request indexing in Search Console to speed up)
3. **Week 2-4**: Stars start appearing in search results
4. **Month 1-2**: Full rollout across all indexed product pages

Google does NOT guarantee rich snippet display. Having valid structured data is necessary but not sufficient — Google decides based on page quality, domain authority, and trust signals.

---

## Complete working example

This is the exact JSON-LD structure deployed on freemoov.com that passes Google validation:

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Trottinette electrique Dualtron Togo Limited",
  "description": "La Dualtron Togo Limited offre vitesse, confort et securite...",
  "url": "https://www.freemoov.com/shop/trottinette-electrique-dualtron-togo-limited-2096",
  "image": ["https://www.freemoov.com/web/image/product.template/2096/image_1920"],
  "sku": "DUALTRON-TOGO-LTD",
  "gtin13": "8809824680123",
  "brand": {
    "@type": "Brand",
    "name": "Dualtron"
  },
  "weight": {
    "@type": "QuantitativeValue",
    "value": 23.5,
    "unitCode": "KGM"
  },
  "offers": {
    "@type": "Offer",
    "url": "https://www.freemoov.com/shop/trottinette-electrique-dualtron-togo-limited-2096",
    "priceCurrency": "EUR",
    "price": "899.00",
    "priceValidUntil": "2026-06-26",
    "availability": "https://schema.org/InStock",
    "itemCondition": "https://schema.org/NewCondition",
    "seller": {"@type": "Organization", "name": "Freemoov"},
    "shippingDetails": [
      {
        "@type": "OfferShippingDetails",
        "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "BE"},
        "shippingRate": {"@type": "MonetaryAmount", "value": 0.00, "currency": "EUR"},
        "deliveryTime": {
          "@type": "ShippingDeliveryTime",
          "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 2, "unitCode": "DAY"},
          "transitTime": {"@type": "QuantitativeValue", "minValue": 2, "maxValue": 5, "unitCode": "DAY"}
        }
      }
    ],
    "hasMerchantReturnPolicy": {
      "@type": "MerchantReturnPolicy",
      "applicableCountry": ["BE", "FR", "LU", "NL"],
      "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
      "merchantReturnDays": 14,
      "returnMethod": ["https://schema.org/ReturnByMail", "https://schema.org/ReturnInStore"],
      "returnFees": "https://schema.org/ReturnFeesCustomerResponsibility"
    }
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.8",
    "reviewCount": 350,
    "bestRating": 5,
    "worstRating": 1
  },
  "review": [
    {
      "@type": "Review",
      "author": {"@type": "Person", "name": "Anthony Fockenoy"},
      "datePublished": "2026-02-10",
      "reviewBody": "Merci pour l'accompagnement, tres bonne experience. Equipe au top, je recommande vivement Freemoov.",
      "reviewRating": {"@type": "Rating", "ratingValue": 5, "bestRating": 5}
    },
    {
      "@type": "Review",
      "author": {"@type": "Person", "name": "Kevin Radogewski"},
      "datePublished": "2026-02-25",
      "reviewBody": "Super service, livraison rapide et equipe disponible pour les conseils. Trottinette top !",
      "reviewRating": {"@type": "Rating", "ratingValue": 5, "bestRating": 5}
    },
    {
      "@type": "Review",
      "author": {"@type": "Person", "name": "Daniel Chantriaux"},
      "datePublished": "2026-02-12",
      "reviewBody": "Communication excellente, equipe au top, bon suivi par mail et WhatsApp. A l'ecoute et reactif.",
      "reviewRating": {"@type": "Rating", "ratingValue": 5, "bestRating": 5}
    }
  ]
}
```
