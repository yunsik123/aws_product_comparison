"""Streamlit UI for product comparison."""
import streamlit as st
import httpx
import os
from datetime import datetime

# Backend API URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Page config
st.set_page_config(
    page_title="농심 제품 비교",
    page_icon="🍜",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .product-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin: 10px 0;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border-left: 4px solid #667eea;
    }
    .warning-box {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .pros-box {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 10px 15px;
        border-radius: 5px;
    }
    .cons-box {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 10px 15px;
        border-radius: 5px;
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 25px;
        font-weight: bold;
    }
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🍜 농심 vs 경쟁사 제품 비교")
st.markdown("실시간 가격, 별점, 리뷰 비교 분석")
st.divider()

# Sidebar - Input Form
with st.sidebar:
    st.header("🔍 비교 설정")
    
    st.subheader("농심 제품")
    brand_a = "농심"
    product_a = st.text_input("제품명", value="신라면", key="product_a")
    
    st.subheader("비교 대상")
    brand_b = st.text_input("브랜드", value="오뚜기", key="brand_b")
    product_b = st.text_input("제품명", value="진라면 매운맛", key="product_b")
    
    st.subheader("데이터 소스")
    source_11st = st.checkbox("11번가", value=True)
    source_danawa = st.checkbox("다나와", value=True)
    source_naver = st.checkbox("네이버 (SerpApi)", value=False)
    source_scrape = st.checkbox("스크래핑 (Fallback)", value=False, disabled=True)
    
    sources = []
    if source_11st:
        sources.append("11st")
    if source_danawa:
        sources.append("danawa")
    if source_naver:
        sources.append("naver_serpapi")
    if source_scrape:
        sources.append("scrape")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        compare_btn = st.button("🔍 비교하기", use_container_width=True)
    with col2:
        force_refresh = st.button("🔄 새로고침", use_container_width=True)


def format_price(price):
    """Format price with comma separators."""
    if price is None:
        return "정보 없음"
    return f"{price:,}원"


def format_rating(rating):
    """Format rating with stars."""
    if rating is None:
        return "정보 없음"
    stars = "⭐" * int(rating) + "☆" * (5 - int(rating))
    return f"{rating:.1f} {stars}"


def display_product_card(product, col):
    """Display a product card in the given column."""
    with col:
        best_offer = product.get("best_offer")
        
        if best_offer:
            st.markdown(f"### {product['brand']} {product['query']}")
            
            # Image
            if best_offer.get("image_url"):
                st.image(best_offer["image_url"], use_container_width=True)
            
            # Metrics
            st.metric("💰 가격", format_price(best_offer.get("price_krw")))
            st.metric("⭐ 별점", format_rating(best_offer.get("rating")))
            st.metric("💬 리뷰 수", f"{best_offer.get('review_count', 0):,}개" if best_offer.get('review_count') else "정보 없음")
            
            # Source and URL
            st.caption(f"출처: {best_offer.get('source', 'N/A')}")
            if best_offer.get("url"):
                st.link_button("🔗 상품 페이지", best_offer["url"])
        else:
            st.warning("제품 정보를 찾을 수 없습니다.")
        
        # Key Features
        st.subheader("📋 주요 특징")
        key_features = product.get("key_features", [])
        if key_features:
            for feature in key_features:
                st.markdown(f"• {feature}")
        else:
            st.caption("정보 없음")
        
        # Pros
        st.subheader("👍 장점")
        pros = product.get("pros", [])
        if pros:
            for pro in pros:
                st.markdown(f"<div class='pros-box'>✓ {pro}</div>", unsafe_allow_html=True)
        else:
            st.caption("정보 없음")
        
        # Cons
        st.subheader("👎 단점")
        cons = product.get("cons", [])
        if cons:
            for con in cons:
                st.markdown(f"<div class='cons-box'>✗ {con}</div>", unsafe_allow_html=True)
        else:
            st.caption("정보 없음")


def display_comparison_table(data):
    """Display comparison metrics table."""
    st.subheader("📊 비교 분석")
    
    comparison = data.get("comparison", {})
    product_a = data.get("product_a", {})
    product_b = data.get("product_b", {})
    
    best_a = product_a.get("best_offer", {}) or {}
    best_b = product_b.get("best_offer", {}) or {}
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 항목")
        st.markdown("**가격**")
        st.markdown("**별점**")
        st.markdown("**리뷰 수**")
    
    with col2:
        st.markdown(f"### {product_a.get('brand', '')} {product_a.get('query', '')}")
        st.markdown(format_price(best_a.get("price_krw")))
        st.markdown(format_rating(best_a.get("rating")))
        st.markdown(f"{best_a.get('review_count', 0):,}개" if best_a.get('review_count') else "정보 없음")
    
    with col3:
        st.markdown(f"### {product_b.get('brand', '')} {product_b.get('query', '')}")
        st.markdown(format_price(best_b.get("price_krw")))
        st.markdown(format_rating(best_b.get("rating")))
        st.markdown(f"{best_b.get('review_count', 0):,}개" if best_b.get('review_count') else "정보 없음")
    
    # Difference summary
    st.divider()
    diff_col1, diff_col2, diff_col3 = st.columns(3)
    
    with diff_col1:
        price_diff = comparison.get("price_diff_krw")
        if price_diff is not None:
            color = "green" if price_diff < 0 else "red" if price_diff > 0 else "gray"
            st.metric("가격 차이", f"{price_diff:+,}원", delta_color="inverse")
    
    with diff_col2:
        rating_diff = comparison.get("rating_diff")
        if rating_diff is not None:
            st.metric("별점 차이", f"{rating_diff:+.2f}")
    
    with diff_col3:
        review_diff = comparison.get("review_count_diff")
        if review_diff is not None:
            st.metric("리뷰 수 차이", f"{review_diff:+,}개")


def fetch_comparison(product_a, brand_b, product_b, sources, force=False):
    """Fetch comparison data from the backend API."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BACKEND_URL}/compare",
                json={
                    "brand_a": "농심",
                    "product_a": product_a,
                    "brand_b": brand_b,
                    "product_b": product_b,
                    "sources": sources,
                    "force_refresh": force
                }
            )
            
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 429:
                return None, "레이트 리밋 초과. 1분 후 다시 시도해주세요."
            else:
                return None, f"API 오류: {response.status_code}"
    except httpx.ConnectError:
        return None, "백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요."
    except Exception as e:
        return None, f"요청 오류: {str(e)}"


# Main content area
if compare_btn or force_refresh:
    if not sources:
        st.error("최소 하나의 데이터 소스를 선택해주세요.")
    else:
        with st.spinner("제품 정보를 수집하고 분석 중입니다..."):
            data, error = fetch_comparison(
                product_a, brand_b, product_b, sources, 
                force=force_refresh
            )
        
        if error:
            st.error(error)
        elif data:
            # Cache status
            if data.get("cached"):
                st.info("📦 캐시된 결과를 표시합니다. 최신 데이터를 보려면 '새로고침'을 클릭하세요.")
            
            # Warnings
            warnings = data.get("warnings", [])
            if warnings:
                with st.expander("⚠️ 경고 메시지", expanded=False):
                    for warning in warnings:
                        st.warning(warning)
            
            # Product comparison
            col1, col2 = st.columns(2)
            display_product_card(data.get("product_a", {}), col1)
            display_product_card(data.get("product_b", {}), col2)
            
            st.divider()
            
            # Comparison table
            display_comparison_table(data)
            
            # Metadata
            st.divider()
            st.caption(f"Request ID: {data.get('request_id', 'N/A')}")
            st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.error("데이터를 가져오는데 실패했습니다.")
else:
    # Default state - show instructions
    st.info("👈 좌측에서 비교할 제품을 선택하고 '비교하기'를 클릭하세요.")
    
    # Sample preview
    st.markdown("""
    ### 🎯 사용 방법
    
    1. **농심 제품 입력**: 비교할 농심 제품명을 입력합니다 (예: 신라면, 안성탕면)
    2. **경쟁사 제품 입력**: 비교 대상 브랜드와 제품명을 입력합니다
    3. **데이터 소스 선택**: 데이터를 수집할 소스를 선택합니다
    4. **비교하기 클릭**: 실시간으로 데이터를 수집하고 분석합니다
    
    ### 📊 제공 정보
    
    - 💰 **가격 비교**: 각 소스에서 수집한 최저가
    - ⭐ **별점 비교**: 고객 평점 비교
    - 💬 **리뷰 분석**: 리뷰 수 및 주요 내용 요약
    - 👍👎 **장단점**: AI 분석을 통한 제품 장단점
    """)
