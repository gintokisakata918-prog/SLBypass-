from app.resolver.extract import choose_destination, extract_candidates

HTML = """
<script>window.location.href = "https://vplink.in/go/abc";</script>
<a href="https://example.com/file.mkv">Download</a>
<a href="https://www.google-analytics.com/collect">ga</a>
"""


def test_picks_destination_over_tracker():
    cands = extract_candidates(HTML, "https://vplink.in/D617Y")
    assert choose_destination(cands, "vplink.in", "https://vplink.in/D617Y") == "https://example.com/file.mkv"


def test_skips_shortener_hosts():
    cands = ["https://vplink.in/go/x", "https://cdn.site.org/a.zip"]
    assert choose_destination(cands, "vplink.in", "https://vplink.in/x") == "https://cdn.site.org/a.zip"
