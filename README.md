# 馃帗 Kaoyan Agent 鈥?鑰冪爺鎷╂牎鏅鸿兘鍔╂墜

> 鍩轰簬 AI 鐨勮€冪爺闄㈡牎鍒嗘瀽涓庡織鎰垮～鎶ヨ緟鍔╃郴缁?
## 鉁?鍔熻兘

- 馃攳 **闄㈡牎鎼滅储** 鈥?鎸変笓涓氥€佸湴鍖恒€佸眰娆＄簿鍑嗘悳绱㈠叏鍥介櫌鏍?- 馃搳 **鍒嗘暟绾垮垎鏋?* 鈥?鍘嗗勾鍥藉绾裤€侀櫌鏍＄嚎鍙鍖栧姣?- 馃 **AI 鏅鸿兘鍒嗘瀽** 鈥?鏍规嵁涓汉鑳屾櫙鎺ㄨ崘鍖归厤闄㈡牎
- 馃挰 **闇€姹傚垎鏋愬璇?* 鈥?涓?AI 瀵硅瘽姊崇悊鎷╂牎闇€姹?- 馃搵 **涓汉鐢诲儚** 鈥?寤虹珛鑰冪爺 Profile锛屼釜鎬у寲鎺ㄨ崘
- 馃幆 **鏅鸿兘鍐崇瓥** 鈥?AI 杈呭姪鍒跺畾蹇楁効濉姤鏂规

## 馃洜锔?鎶€鏈爤

### 鍚庣
- **Python** / **FastAPI** 鈥?API 妗嗘灦
- **SQLAlchemy** + **Alembic** 鈥?鏁版嵁搴?ORM 涓庤縼绉?- **ChromaDB** 鈥?鍚戦噺鏁版嵁搴擄紙AI 妫€绱㈠寮猴級
- **APScheduler** 鈥?瀹氭椂浠诲姟
- **BeautifulSoup / aiohttp** 鈥?鏁版嵁鐖彇

### 鍓嶇
- **React 19** + **TypeScript**
- **Vite** 鈥?鏋勫缓宸ュ叿
- **TailwindCSS 4** 鈥?鏍峰紡
- **Recharts** 鈥?鍥捐〃鍙鍖?- **React Router** 鈥?璺敱
- **Playwright** 鈥?E2E 娴嬭瘯

## 馃殌 蹇€熷紑濮?
### 鍚庣

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
# 閰嶇疆 .env锛堝弬鑰?.env.example锛?uvicorn app.main:app --reload
```

### 鍓嶇

```bash
cd frontend
npm install
npm run dev
```

## 馃椇锔?椤圭洰缁撴瀯

```
kaoyan-agent/
鈹溾攢鈹€ backend/                 # FastAPI 鍚庣
鈹?  鈹溾攢鈹€ app/
鈹?  鈹?  鈹溾攢鈹€ api/            # API 璺敱
鈹?  鈹?  鈹溾攢鈹€ agents/         # AI Agent 閫昏緫
鈹?  鈹?  鈹溾攢鈹€ services/       # 涓氬姟鏈嶅姟灞?鈹?  鈹?  鈹溾攢鈹€ models/         # 鏁版嵁妯″瀷
鈹?  鈹?  鈹溾攢鈹€ db/             # 鏁版嵁搴撻厤缃?鈹?  鈹?  鈹溾攢鈹€ data/           # 鏁版嵁鏄犲皠
鈹?  鈹?  鈹溾攢鈹€ middleware/     # 涓棿浠?鈹?  鈹?  鈹斺攢鈹€ utils/          # 宸ュ叿鍑芥暟
鈹?  鈹溾攢鈹€ migrations/         # 鏁版嵁搴撹縼绉?鈹?  鈹溾攢鈹€ scripts/            # 鏁版嵁鐖彇涓庡鍏ヨ剼鏈?鈹?  鈹斺攢鈹€ tests/              # 娴嬭瘯
鈹溾攢鈹€ frontend/               # React 鍓嶇
鈹?  鈹斺攢鈹€ src/
鈹?      鈹溾攢鈹€ pages/          # 椤甸潰
鈹?      鈹溾攢鈹€ components/     # 缁勪欢
鈹?      鈹斺攢鈹€ api/            # API 瀹㈡埛绔?鈹斺攢鈹€ docs/                   # 鏂囨。
```

## 馃搫 璁稿彲璇?
MIT
