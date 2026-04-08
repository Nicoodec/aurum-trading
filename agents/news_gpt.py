import os, json, requests, re
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("OPENAI_API_KEY", "")

def analyze_news_gpt(news_items):
    if not KEY or not news_items:
        return None
    try:
        hl = chr(10).join(["- ["+i["source"]+"] "+i["title"] for i in news_items[:20]])
        q1 = chr(34)
        prompt = (
            "You are a gold XAU/USD trading analyst. Analyze these news headlines."+chr(10)+
            "Respond ONLY in valid JSON with these exact fields:"+chr(10)+
            "{"+q1+"sentiment"+q1+":"+q1+"BULLISH_GOLD"+q1+","+q1+"confidence"+q1+":75,"+
            q1+"key_events"+q1+":["+q1+"event1"+q1+"],"+
            q1+"scheduled_events"+q1+":[],"+
            q1+"bull_factors"+q1+":["+q1+"factor1"+q1+"],"+
            q1+"bear_factors"+q1+":["+q1+"factor1"+q1+"],"+
            q1+"summary"+q1+":"+q1+"2 sentence analysis"+q1+"}"+chr(10)+chr(10)+
            "HEADLINES:"+chr(10)+hl
        )
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer "+KEY, "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            },
            timeout=25
        )
        data = r.json()
        if "error" in data:
            print("[gpt] API error:", data["error"].get("message","")[:100])
            return None
        if "choices" not in data:
            print("[gpt] unexpected response:", str(data)[:200])
            return None
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        return result
    except Exception as e:
        print("[gpt] error:", e)
        return None
