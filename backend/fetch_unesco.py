# backend/fetch_unesco.py
import httpx
import json

API_ENDPOINT = "https://data.unesco.org/api/explore/v2.0"  # 替换实际参数

def fetch_all():
    params = {
        # 根据 API 控制台提示设置分页、过滤参数
        "rows": 1000,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(API_ENDPOINT, params=params)
        resp.raise_for_status()
        return resp.json()

def main():
    data = fetch_all()
    # 假设返回 data['records']
    records = data.get('records', [])
    # 简化保存
    with open("../data/unesco_ich.json", 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"保存了 {len(records)} 条记录")

if __name__ == "__main__":
    main()
