import os
from newsapi import NewsApiClient

client = NewsApiClient(api_key=os.getenv("NEWSAPI_KEY", ""))
response = client.get_top_headlines(language="en", page_size=5)
print(f"Status: {response['status']}")
print(f"Total results: {response['totalResults']}")
for a in response.get("articles", [])[:3]:
    print(f"  - {a['title']}")