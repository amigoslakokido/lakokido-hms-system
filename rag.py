# rag.py
# بسيط وخفيف: يبحث في ملفات نصية داخل مجلد "kb" ويُرجع أفضل K مقتطفات كـ context.

from pathlib import Path
import re

KB_DIR = Path(__file__).parent / "kb"

def _load_docs():
    docs = []
    if KB_DIR.exists():
        for p in KB_DIR.glob("*.txt"):
            try:
                docs.append((p.name, p.read_text(encoding="utf-8")))
            except Exception:
                pass
    return docs

def top_k(query: str, k: int = 3):
    """
    يرجّع قائمة قوامها dicts كل عنصر فيه:
    { "title": <اسم الملف>, "content": <النص الكامل> }
    لو ما في مجلد kb أو ما في تطابق، ترجع قائمة فاضية.
    """
    if not query:
        return []

    q = query.lower()
    docs = _load_docs()
    if not docs:
        return []

    scored = []
    # درجة بسيطة: عدد كلمات الاستعلام الموجودة في النص
    q_words = re.findall(r"\w+", q)
    for name, text in docs:
        t = text.lower()
        score = sum(1 for w in q_words if w in t)
        if score > 0:
            scored.append((score, name, text))

    scored.sort(reverse=True, key=lambda x: x[0])
    top = scored[:k]
    return [{"title": name, "content": text} for _, name, text in top]
