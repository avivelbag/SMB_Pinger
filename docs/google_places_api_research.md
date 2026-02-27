# Google Places API Research: Business Website Lookup

**Date:** 2026-02-26
**Use Case:** Given a business name + location (Santa Barbara, CA), find their website URL.

---

## 1. Which API to Use

### Use Places API (New), NOT Legacy

- **Places API (New)** is the current, actively-supported version.
- **Places API (Legacy)** can no longer be enabled for new projects and is deprecated.
- The New API uses **POST requests** (not GET), with JSON bodies and a required `FieldMask` header.

### Recommended Endpoint: Text Search (New)

**Endpoint:** `POST https://places.googleapis.com/v1/places:searchText`

Text Search is the best fit for "business name + city" lookups because:
- It accepts natural language queries like `"Joe's Cafe Santa Barbara CA"`
- It returns multiple candidates ranked by relevance
- You can request only the fields you need (cost control via FieldMask)
- It supports `locationBias` to favor results near a geographic point

**Why not Find Place?** Find Place (Legacy) was the old lightweight option for this, but
it has been deprecated. Text Search (New) subsumes its functionality.

**Why not Place Details?** Place Details requires a `place_id` you already have. It's a
second step if you need to enrich data after a search, not a starting point.

### Optimal Flow

```
1. Text Search (New): "BusinessName Santa Barbara CA"
   → Returns place_id, displayName, websiteUri, formattedAddress
   → Take the first result (highest relevance)
   → Extract websiteUri

2. (Optional) Place Details (New): only if websiteUri was empty in step 1
   → Use the place_id from step 1
   → Request only websiteUri field
```

For most businesses, step 1 alone suffices.

---

## 2. Pricing (Post-March 2025)

### Free Tier Changes

As of **March 1, 2025**, Google replaced the universal $200/month credit with
**per-SKU free usage thresholds**:

| SKU Category  | Free Requests/Month |
|---------------|---------------------|
| Essentials    | 10,000              |
| Pro           | 5,000               |
| Enterprise    | 1,000               |

### Which SKU Does `websiteUri` Trigger?

The `websiteUri` field triggers the **Text Search Enterprise** SKU.

**This means: requesting the website URL = Enterprise tier pricing.**

### Text Search Enterprise Pricing

| Monthly Volume          | Cost per 1,000 Requests |
|-------------------------|-------------------------|
| 0 - 100,000             | ~$32.00                 |
| 100,001 - 500,000       | Volume discount (~20%)  |
| 500,001+                | Greater discounts       |

### How Many Free Lookups?

With the Enterprise SKU, you get **1,000 free requests/month**.

At ~$32/1,000 requests = **$0.032 per request** after the free tier.

### Cost Optimization Strategy

**Option A: Single Text Search call (recommended for simplicity)**
- Include `websiteUri` in the FieldMask → triggers Enterprise SKU
- 1,000 free/month, then $0.032 each

**Option B: Two-step approach (cheaper if many businesses lack websites)**
1. Text Search with Pro-tier fields only (displayName, formattedAddress, id)
   → 5,000 free/month, ~$20/1,000 after
2. Place Details for websiteUri only on results that matter
   → Separate Enterprise charge only when needed

**For ~200-500 businesses total, Option A stays within the 1,000 free tier.**

---

## 3. Python Client Options

### Option A: `httpx` / `requests` (Recommended for New API)

The `googlemaps` Python library (`pip install googlemaps`) primarily supports the
**Legacy** Places API. It does NOT have first-class support for the Places API (New)
POST-based endpoints.

**Use `httpx` directly against the REST API.** This gives you full control over the
New API's features including FieldMask headers.

```python
import httpx
from typing import Optional

GOOGLE_API_KEY = "YOUR_API_KEY"
PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Santa Barbara, CA coordinates
SANTA_BARBARA_LAT = 34.4208
SANTA_BARBARA_LNG = -119.6982

async def lookup_business_website(
    business_name: str,
    city: str = "Santa Barbara, CA",
    api_key: str = GOOGLE_API_KEY,
) -> Optional[str]:
    """Look up a business website URL using Google Places Text Search (New)."""

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Only request fields we need - this controls billing SKU
        "X-Goog-FieldMask": "places.id,places.displayName,places.websiteUri,places.formattedAddress",
    }

    body = {
        "textQuery": f"{business_name} {city}",
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": SANTA_BARBARA_LAT,
                    "longitude": SANTA_BARBARA_LNG,
                },
                "radius": 25000.0,  # 25km radius covers Santa Barbara metro
            }
        },
        "pageSize": 1,  # We only need the top result
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            PLACES_TEXT_SEARCH_URL,
            headers=headers,
            json=body,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    places = data.get("places", [])
    if not places:
        return None

    top_result = places[0]
    return top_result.get("websiteUri")


# Synchronous version
def lookup_business_website_sync(
    business_name: str,
    city: str = "Santa Barbara, CA",
    api_key: str = GOOGLE_API_KEY,
) -> Optional[str]:
    """Synchronous version of business website lookup."""

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.websiteUri,places.formattedAddress",
    }

    body = {
        "textQuery": f"{business_name} {city}",
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": SANTA_BARBARA_LAT,
                    "longitude": SANTA_BARBARA_LNG,
                },
                "radius": 25000.0,
            }
        },
        "pageSize": 1,
    }

    response = httpx.post(
        PLACES_TEXT_SEARCH_URL,
        headers=headers,
        json=body,
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    places = data.get("places", [])
    if not places:
        return None

    return places[0].get("websiteUri")
```

### Option B: `google-maps-places` (Official gRPC Client)

There IS a separate official client for Places API (New):
```
pip install google-maps-places
```

This is the `google.maps.places` package (not the `googlemaps` package).
It uses gRPC, has auto-generated code, and is heavier. The REST/httpx approach
above is simpler and more transparent for this use case.

### Option C: `googlemaps` (Legacy Only - NOT Recommended)

```
pip install googlemaps
```

This supports legacy `find_place()` and `places()` but NOT the New API.
The legacy API is deprecated and may stop working. Avoid for new projects.

---

## 4. Rate Limits and Quotas

### Default Limits

- **Per-method quota:** Each API method (Text Search, Place Details, etc.) has its
  own separate rate limit per project
- **Default:** ~600 requests per minute (RPM) per method per project (adjustable
  in Cloud Console)
- **No hard daily limit:** billing is usage-based; you can set budget alerts and
  caps in the Cloud Console

### Throttling Behavior

- When you exceed QPS/RPM: HTTP 429 "RESOURCE_EXHAUSTED" response
- Google recommends **exponential backoff** for retries

### How to Handle Throttling in Python

```python
import httpx
import asyncio
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception

def is_rate_limited(exception):
    return (
        isinstance(exception, httpx.HTTPStatusError)
        and exception.response.status_code == 429
    )

@retry(
    retry=retry_if_exception(is_rate_limited),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5),
)
async def lookup_with_retry(business_name: str, **kwargs):
    return await lookup_business_website(business_name, **kwargs)
```

### Practical Advice for This Project

For looking up ~200-500 Santa Barbara businesses:
- At 1 request per second, the full batch completes in ~5-8 minutes
- Rate limiting is unlikely to be an issue at this scale
- Add a small delay (0.1-0.5s) between requests to be safe

---

## 5. Response Fields for Website URL

### Field Name: `websiteUri`

In the Places API (New), the website field is called **`websiteUri`** (not `website`
as in the Legacy API).

**FieldMask value:** `places.websiteUri`

### Example Response

```json
{
  "places": [
    {
      "id": "ChIJ...",
      "displayName": {
        "text": "Joe's Cafe",
        "languageCode": "en"
      },
      "formattedAddress": "536 State St, Santa Barbara, CA 93101, USA",
      "websiteUri": "https://www.joescafesb.com/"
    }
  ]
}
```

### Data Reliability

- **websiteUri** is populated from Google Business Profile data (claimed by owners)
  and Google's crawling/data collection.
- **Not 100% populated:** Many small businesses do not have a website listed.
  The field may be absent from the response entirely.
- **May be outdated:** Business websites change; Google's data can lag.
- **May be a social media page:** Some businesses list their Facebook/Instagram
  page as their "website."
- **Generally reliable for established businesses** that have claimed their
  Google Business Profile.

### Fields to Request (Recommended FieldMask)

```
places.id,places.displayName,places.websiteUri,places.formattedAddress
```

Adding more fields increases the SKU tier and cost. Keep it minimal.

---

## 6. Matching Accuracy

### How Good Is Text Search at Finding the Right Business?

- **Generally excellent** for queries like "BusinessName CityName State"
- Results are ranked by **relevance** (text match) and **prominence** (reviews,
  ratings, popularity)
- Including the full business name + "Santa Barbara CA" in the textQuery gives
  strong matching

### Tips for Improving Match Accuracy

1. **Include the city and state in the textQuery:**
   ```python
   textQuery = f"{business_name} Santa Barbara, CA"
   ```

2. **Use `locationBias` with a circle around Santa Barbara:**
   ```json
   {
     "locationBias": {
       "circle": {
         "center": {"latitude": 34.4208, "longitude": -119.6982},
         "radius": 25000.0
       }
     }
   }
   ```
   Note: If the textQuery already contains "Santa Barbara", the explicit location
   in the query takes priority over locationBias. Both together still help.

3. **Use `locationRestriction` instead of `locationBias` for strict filtering:**
   If you want to ONLY get results within the Santa Barbara area (no results from
   other cities), use locationRestriction with a bounding rectangle.

4. **Set `pageSize: 1`** if you only want the top match (saves processing time).

5. **Validate the result:** Compare the `formattedAddress` in the response to
   confirm it's in Santa Barbara. Flag results outside the expected area.

6. **Handle ambiguity:** Common business names (e.g., "Subway", "Pizza Hut")
   may match the wrong location. Including street address or neighborhood helps.

### Expected Accuracy

- For unique business names in Santa Barbara: **>95% match rate**
- For common/chain business names: **~80-90%** (may need address disambiguation)
- Website URL populated when matched: **~60-80%** of small businesses have a
  website listed in Google's data

---

## 7. Caching and Terms of Service

### What the ToS Says

Per [Google Maps Platform Service Specific Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms):

| Data Type             | Caching Allowed?                          |
|-----------------------|-------------------------------------------|
| `place_id`            | YES - cache indefinitely (refresh if >12 months old) |
| `websiteUri`          | NO - cannot be cached or stored           |
| Lat/lng coordinates   | Temporary cache up to 30 consecutive days |
| All other content     | NO - must not pre-fetch, index, or store  |

### What This Means for the Project

**You CANNOT permanently store website URLs** retrieved from the Places API
in a database or file, per the ToS.

However, you CAN:
1. **Cache `place_id` values** indefinitely (store in your database)
2. **Use the website URL transiently** (e.g., to immediately ping/check the site,
   then discard the cached URL)
3. **Re-fetch as needed** using stored place_ids via Place Details

### Practical Approach

```python
# Store this (allowed):
cached_data = {
    "business_name": "Joe's Cafe",
    "place_id": "ChIJ...",        # Can be stored indefinitely
    "last_lookup": "2026-02-26",
}

# Use this transiently, do NOT persist (per ToS):
website_url = "https://www.joescafesb.com/"
# → Immediately use it (e.g., ping the website)
# → Do NOT save to a database for long-term storage
```

### Important Caveat

Many applications in practice DO store Google Places data. Enforcement is
unclear. But if you want to be ToS-compliant:
- Store place_ids
- Re-query for fresh websiteUri values each time you need them
- Or find the website through an independent means (e.g., scraping Google
  search results, which has its own ToS considerations)

---

## Summary: Recommended Implementation

| Decision                | Choice                                          |
|-------------------------|-------------------------------------------------|
| API Version             | Places API (New)                                |
| Endpoint                | Text Search (`places:searchText`)               |
| HTTP Client             | `httpx` (direct REST calls)                     |
| Field Mask              | `places.id,places.displayName,places.websiteUri,places.formattedAddress` |
| SKU Triggered           | Text Search Enterprise                          |
| Cost per Request        | ~$0.032 (after 1,000 free/month)                |
| Free Tier               | 1,000 requests/month                            |
| Rate Limiting           | ~600 RPM default, use exponential backoff       |
| Caching                 | Store place_id only; website URL is transient    |

### Quick Start Checklist

1. Create a Google Cloud project
2. Enable "Places API (New)" in the API Library
3. Create an API key (restrict to Places API)
4. Set up billing (required, but 1,000 free Enterprise requests/month)
5. Use the Python code above with httpx
6. Monitor usage in Cloud Console > APIs & Services > Dashboard
