def page_text(at):
    """AppTest 화면의 텍스트를 합친다 (전역 <style> 제외)."""
    parts = [m.value for m in at.markdown if not m.value.lstrip().startswith("<style>")]
    for group in (at.caption, at.warning, at.info, at.error, at.success):
        parts += [e.value for e in group]
    return "\n".join(parts)
