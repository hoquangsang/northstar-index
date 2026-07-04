from __future__ import annotations

from app.ingestion.html_cleaner import clean_html


def test_clean_html_removes_noise_and_absolutizes_links() -> None:
    html = """
    <article>
      <nav>Menu</nav>
      <script>alert("x")</script>
      <p>Read <a href="/hc/en-us/articles/123-Test">this</a>.</p>
      <img src="/assets/demo.png"/>
    </article>
    """

    cleaned = clean_html(html, base_url="https://support.optisigns.com")

    assert "Menu" not in cleaned
    assert "alert" not in cleaned
    assert 'href="https://support.optisigns.com/hc/en-us/articles/123-Test"' in cleaned
    assert 'src="https://support.optisigns.com/assets/demo.png"' in cleaned
