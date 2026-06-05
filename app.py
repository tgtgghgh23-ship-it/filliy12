import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import altair as alt

# 스트림릿 페이지 설정 (아이콘 및 반응형 레이아웃 구성)
st.set_page_config(
    page_title="삼성전자 주가 & 이슈 분석기",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="expanded"
)

# 사이드바 설정
st.sidebar.title("📈 주식 분석기")
st.sidebar.markdown("삼성전자의 가격 흐름과 당일/전일 뉴스 헤드라인을 분석하는 도구입니다.")
st.sidebar.caption("Powered by Naver FChart & Google News")

# ==========================================
# 주식 & 이슈 분석기 비즈니스 로직 및 컴포넌트
# ==========================================

def get_stock_data(symbol, count=100):
    """네이버 금융 FChart XML API를 이용해 일별 시세 데이터 획득"""
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={symbol}&timeframe=day&count={count}&requestType=0"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            import xml.etree.ElementTree as ET
            # Decode to unicode string using EUC-KR encoding
            xml_text = r.content.decode('euc-kr', errors='replace')
            # Remove XML declaration to prevent multi-byte encoding error in standard ElementTree
            if xml_text.startswith("<?xml"):
                idx = xml_text.find("?>")
                if idx != -1:
                    xml_text = xml_text[idx+2:]
            
            root = ET.fromstring(xml_text.strip())
            data = []
            for item in root.findall('.//item'):
                row = item.attrib['data'].split('|')
                # Date(YYYYMMDD), Open, High, Low, Close, Volume
                if len(row) >= 6:
                    data.append({
                        'Date': row[0],
                        'Open': float(row[1]),
                        'High': float(row[2]),
                        'Low': float(row[3]),
                        'Close': float(row[4]),
                        'Volume': int(row[5])
                    })
            df = pd.DataFrame(data)
            if not df.empty:
                df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
                df = df.sort_values('Date').reset_index(drop=True)
                return df
    except Exception as e:
        st.error(f"주가 조회 중 오류 발생: {str(e)}")
    return None


def get_news_for_date(keyword, target_date):
    """구글 뉴스 RSS를 사용하여 특정 날짜의 하루 전(Date - 1)과 당일(Date) 뉴스 헤드라인 검색"""
    from datetime import timedelta
    import xml.etree.ElementTree as ET
    
    # after/before는 경계값을 포함하지 않으므로 하루 전과 당일을 포함하도록 기간 설정
    # after: target_date - 2일 (초과이므로 target_date-1일부터 포함)
    # before: target_date + 1일 (미만이므로 target_date일까지 포함)
    start_date = target_date - timedelta(days=2)
    end_date = target_date + timedelta(days=1)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    query = f"{keyword} after:{start_str} before:{end_str}"
    quoted_query = requests.utils.quote(query)
    
    url = f"https://news.google.com/rss/search?q={quoted_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            news_list = []
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                source = item.find('source').text if item.find('source') is not None else ""
                
                clean_title = title
                if " - " in title:
                    clean_title = " - ".join(title.split(" - ")[:-1])
                
                news_list.append({
                    'title': clean_title,
                    'link': link,
                    'pubDate': pubDate,
                    'source': source
                })
            return news_list
    except Exception:
        pass
    return []


st.title("📊 삼성전자 주가 & 이슈 분석기")
st.markdown("삼성전자의 가격 흐름과 함께 특정 날짜에 어떤 뉴스/이슈가 있었는지 실시간으로 연계하여 주가 변동 원인을 추적합니다.")

# 분석 기간 설정
days_count = st.selectbox("분석 기간 설정", [30, 60, 90, 120], format_func=lambda x: f"최근 {x}일")

stock_code = "005930"
stock_name = "삼성전자"

with st.spinner("네이버 금융에서 주가 정보를 수집하는 중..."):
    df = get_stock_data(stock_code, count=days_count)
    
if df is not None and not df.empty:
    # 주가 계산 변수 생성
    df['Change'] = df['Close'].diff()
    df['Change_Pct'] = (df['Close'].pct_change() * 100).round(2)
    
    # 최신 가격 데이터 메트릭 표시
    latest_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else latest_row
    
    change_val = latest_row['Close'] - prev_row['Close']
    change_pct = ((latest_row['Close'] - prev_row['Close']) / prev_row['Close'] * 100) if prev_row['Close'] > 0 else 0.0
    
    # 주가 정보 메트릭 렌더링
    st.markdown("---")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    
    m_col1.metric("📍 종목명", f"{stock_name} ({stock_code})")
    m_col2.metric(
        "💰 현재가 (종가)", 
        f"{int(latest_row['Close']):,} 원"
    )
    m_col3.metric(
        "📈 전일 대비", 
        f"{int(change_val):+,} 원", 
        delta=f"{change_pct:+.2f}%"
    )
    m_col4.metric(
        "📊 거래량", 
        f"{int(latest_row['Volume']):,} 주"
    )
    
    # 주가 트렌드 차트 (Candlestick Chart using Altair)
    st.markdown("### 🕯️ 주가 가격 추이 (캔들 차트)")
    
    df_chart = df.copy()
    df_chart['is_up'] = df_chart['Close'] > df_chart['Open']
    # 날짜를 YYYY-MM-DD 포맷의 문자열로 변환하여 1일 단위(영업일 기준 주말 갭 없이)로 밀착 나열
    df_chart['Date_Str'] = df_chart['Date'].dt.strftime('%Y-%m-%d')
    
    # 한국인 정서에 맞는 상승(빨강 #EF4444) / 하락(파랑 #2563EB) 색상 매핑
    color_condition = alt.condition(
        "datum.is_up", 
        alt.value("#EF4444"), # 빨강 (상승)
        alt.value("#2563EB")  # 파랑 (하락)
    )
    
    # 1일 단위 순서형(Ordinal)으로 X축 축 설정 및 모든 날짜 레이블 강제 표시
    base = alt.Chart(df_chart).encode(
        x=alt.X('Date_Str:O', title='날짜', axis=alt.Axis(labelAngle=-90, values=df_chart['Date_Str'].tolist()))
    )
    
    # 꼬리선 (High-Low)
    rule = base.mark_rule().encode(
        y=alt.Y('Low:Q', scale=alt.Scale(zero=False), title='주가 (원)'),
        y2='High:Q',
        color=color_condition
    )
    
    # 몸통 (Open-Close)
    bar = base.mark_bar(size=8).encode(
        y='Open:Q',
        y2='Close:Q',
        color=color_condition
    )
    
    # 차트 결합 및 속성 설정
    candlestick_chart = (rule + bar).properties(
        height=350
    ).interactive()
    
    st.altair_chart(candlestick_chart, use_container_width=True)
    
    # 변동성 높은 날들 요약 분석 및 사이드바 배치
    df_for_analysis = df.dropna().copy()
    df_for_analysis['Abs_Change_Pct'] = df_for_analysis['Change_Pct'].abs()
    top_volatile_days = df_for_analysis.nlargest(5, 'Abs_Change_Pct')
    
    # 사이드바에 TOP 5 변동일 배치
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏆 등락률 TOP 5 날짜")
    volatile_table_data = []
    for _, r in top_volatile_days.iterrows():
        d_str = r['Date'].strftime('%Y-%m-%d')
        sign = "+" if r['Change_Pct'] > 0 else ""
        color = "🔴" if r['Change_Pct'] > 0 else "🔵"
        volatile_table_data.append({
            "날짜": d_str,
            "구분": f"{color} 상승" if r['Change_Pct'] > 0 else f"{color} 하락",
            "등락률": f"{sign}{r['Change_Pct']}%"
        })
    st.sidebar.table(pd.DataFrame(volatile_table_data))
    
    # 날짜를 선택할 수 있도록 리스트 포맷 생성
    date_options = {}
    select_list = []
    
    # 일반적인 날짜 리스트 (최신순)
    all_dates_desc = df.dropna().sort_values('Date', ascending=False)
    for _, row in all_dates_desc.iterrows():
        d_str = row['Date'].strftime('%Y-%m-%d')
        day_name = ["월", "화", "수", "목", "금", "토", "일"][row['Date'].weekday()]
        change_sign = "+" if row['Change_Pct'] > 0 else ""
        label = f"{d_str} ({day_name}) | 종가: {int(row['Close']):,}원 ({change_sign}{row['Change_Pct']}%)"
        date_options[label] = row['Date']
        select_list.append(label)
        
    # 기본 선택값 설정 (가장 최근 날짜인 당일이 디폴트로 설정됩니다)
    default_index = 0
    
    # 메인 영역 중앙 배치로 날짜 선택 및 상세 분석 진행
    st.markdown("### ⚡ 주가 변동일 상세 뉴스 분석")
    
    selected_label = st.selectbox(
        "🔍 상세 분석할 날짜를 선택하세요 (최근 등락률이 컸던 날이 자동 선택됩니다):", 
        select_list,
        index=default_index
    )
    chosen_date = date_options[selected_label]
    chosen_row = df[df['Date'] == chosen_date].iloc[0]
    
    # 선택된 날짜의 가격 정보 요약 카드 (중앙 풀 위드 카드)
    c_sign = "+" if chosen_row['Change_Pct'] > 0 else ""
    c_color = "#DC2626" if chosen_row['Change_Pct'] > 0 else "#2563EB"
    bg_color = "#FEF2F2" if chosen_row['Change_Pct'] > 0 else "#EFF6FF"
    border_color = "#FCA5A5" if chosen_row['Change_Pct'] > 0 else "#BFDBFE"
    
    st.markdown(
        f"""
        <div style='background-color:{bg_color}; border: 1px solid {border_color}; border-left: 8px solid {c_color}; padding:20px; border-radius:12px; margin-top:10px; margin-bottom: 25px;'>
            <h3 style='margin:0; color:#1E293B;'>선택한 날짜: {chosen_date.strftime('%Y-%m-%d')} ({["월", "화", "수", "목", "금", "토", "일"][chosen_date.weekday()]})</h3>
            <div style='margin-top: 10px; font-size:18px; color:#334155;'>
                종가: <b style='font-size:22px;'>{int(chosen_row['Close']):,}원</b> | 
                전일대비: <span style='color:{c_color}; font-weight:bold; font-size:22px;'>{chosen_row['Change_Pct']:+.2f}%</span>
            </div>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # 뉴스 로딩 및 기사 목록 표시
    with st.spinner(f"{chosen_date.strftime('%Y-%m-%d')} 하루 전 및 당일 뉴스를 검색 중..."):
        news_data = get_news_for_date(stock_name, chosen_date)
        
    if news_data:
        # 주가 영향 키워드가 포함된 뉴스를 목록 최상단에 우선 배치 (정렬)
        priority_keywords = [
            "상승", "하락", "급등", "급락", "폭등", "폭락", 
            "호재", "악재", "어닝", "쇼크", "서프라이즈", 
            "상한가", "하한가", "반등", "강세", "약세", "실적"
        ]
        news_data = sorted(
            news_data, 
            key=lambda x: 0 if any(kw in x['title'] for kw in priority_keywords) else 1
        )
        
        st.markdown("#### 📰 주요 뉴스 헤드라인 목록")
        
        # 최대 8개 기사 카드 형태로 렌더링
        for item in news_data[:8]:
            title = item['title']
            link = item['link']
            source = item['source']
            
            # 키워드 하이라이트 처리
            keywords = ["실적", "상승", "하락", "급등", "급락", "최고", "최저", "반도체", "신제품", "출시", "계약", "호재", "악재", "어닝", "쇼크", "서프라이즈"]
            highlighted_title = title
            for kw in keywords:
                if kw in highlighted_title:
                    if kw in ["상승", "급등", "호재", "서프라이즈", "최고"]:
                        color = "#DC2626" # 빨강
                    elif kw in ["하락", "급락", "악재", "쇼크", "최저"]:
                        color = "#2563EB" # 파랑
                    else:
                        color = "#D97706" # 오렌지
                    highlighted_title = highlighted_title.replace(kw, f"<span style='color:{color}; font-weight:bold;'>{kw}</span>")
            
            st.markdown(
                f"""
                <div style='padding: 14px; border: 1px solid #F1F5F9; border-radius: 8px; margin-bottom: 12px; background-color: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.02);'>
                    <a href='{link}' target='_blank' style='text-decoration:none; color:#1E293B; font-weight:600; font-size:15px; display:block;'>
                        🔗 {highlighted_title}
                    </a>
                    <div style='color:#94A3B8; font-size:12px; margin-top:6px; text-align:right;'>출처: {source}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.warning("선택하신 날짜 부근에 해당하는 관련 뉴스 기사를 찾지 못했습니다.")
else:
    st.error("삼성전자 주가 정보를 불러오는 데 실패했습니다. 잠시 후 다시 시도해 주세요.")
