"""One-off diagnostic: list every raw dimension field name in the Home Affairs
grant-rates pivot cache, to check whether a visa_subclass field exists that
we aren't currently capturing in import_homeaffairs.py's DIM_FIELD_MAP."""
import io
import time
import zipfile
from xml.etree import ElementTree as ET
import requests

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def get_with_retry(url, timeout=90, tries=3):
    last_exc = None
    for attempt in range(1, tries + 1):
        try:
            print(f"  Attempt {attempt}/{tries}: {url[:80]}...")
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            print(f"    Failed: {exc}")
            time.sleep(3)
    raise last_exc

resp = get_with_retry(
    "https://data.gov.au/data/api/3/action/package_show?id=324aa4f7-46bb-4d56-bc2d-772333a2317e"
)
resources = resp.json()['result']['resources']
url = next(r['url'] for r in resources if 'grant rate' in (r.get('name') or '').lower())

content_resp = get_with_retry(url, timeout=120)
content = content_resp.content

zf = zipfile.ZipFile(io.BytesIO(content))
root = ET.fromstring(zf.read('xl/pivotCache/pivotCacheDefinition1.xml'))
fields = root.findall(f'.//{NS}cacheFields/{NS}cacheField')

print(f"\nTotal fields in pivot cache: {len(fields)}\n")
for f in fields:
    print(f"  - {f.get('name')}")