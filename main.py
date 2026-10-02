from fastapi import FastAPI
import requests
import json
import re

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Render Proxy is running"}

@app.get("/tenders/full-sync")
def full_sync(page: int = 1):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        gem_page_res = requests.get('https://bidplus.gem.gov.in/all-bids', headers=headers, timeout=30)
        gem_html = gem_page_res.text
        
        token_match = re.search(r'csrf_bd_gem_nk[^\'"\n]{0,80}[\'"]\s*:\s*[\'"]([a-zA-Z0-9_-]{20,})', gem_html)
        token = token_match.group(1) if token_match else ''
        cookie = gem_page_res.headers.get('set-cookie', '')

        postdata = {
            "page": page,
            "param": {"searchBid": "", "searchType": "fullText"},
            "filter": {
                "bidStatusType": "ongoing_bids",
                "byType": "all",
                "highBidValue": "",
                "byEndDate": {"from": "", "to": ""},
                "sort": "Bid-End-Date-Oldest"
            }
        }

        api_headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Origin': 'https://bidplus.gem.gov.in',
            'Referer': 'https://bidplus.gem.gov.in/all-bids',
            'Cookie': cookie
        }

        payload = {
            'payload': json.dumps(postdata),
            'csrf_bd_gem_nk': token
        }

        gem_data_res = requests.post('https://bidplus.gem.gov.in/all-bids-data', headers=api_headers, data=payload, timeout=30)
        
        if gem_data_res.status_code != 200:
            return {"error": f"GeM API error {gem_data_res.status_code}"}

        data = gem_data_res.json()

        response_obj = data.get('response', data)
        nested_response = response_obj.get('response', response_obj)
        docs = nested_response.get('docs', [])
        total_available = nested_response.get('numFound', nested_response.get('total', len(docs)))

        tenders = []
        for doc in docs:
            bid_id = doc.get('b_bid_id') or doc.get('b_id') or ''
            tenders.append({
                "bidNumber": doc.get('b_bid_number') or doc.get('bid_number') or '',
                "category": doc.get('bd_category_name') or doc.get('b_category_name') or doc.get('category') or '',
                "quantity": doc.get('b_total_quantity') or doc.get('total_quantity') or '',
                "ministry": doc.get('ba_official_details_minName') or doc.get('ministry') or '',
                "department": doc.get('ba_official_details_deptName') or doc.get('department') or '',
                "startDate": doc.get('final_start_date_sort') or doc.get('start_date') or '',
                "endDate": doc.get('final_end_date_sort') or doc.get('end_date') or '',
                "status": doc.get('bid_status') or 'Active',
                "categoryType": "Medical" if "medical" in (doc.get('bd_category_name') or '').lower() else "Non-Medical",
                "link": f"https://bidplus.gem.gov.in/showbidDocument/{bid_id}" if bid_id else ''
            })

        page_size = len(docs)
        done = page_size == 0 or (page * page_size) >= total_available

        return {
            "tenders": tenders,
            "totalAvailable": total_available,
            "pageSize": page_size,
            "nextPage": None if done else page + 1,
            "done": done
        }

    except Exception as e:
        return {"error": str(e)}
