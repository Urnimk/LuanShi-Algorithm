"""經驗面板精確對應國家與可讀 Q 值。"""

from pathlib import Path
from experience_view import extract_country_experience


def test_exact_country_not_similar_name():
    report = ("戰略 Q 值觀察表\n國家：甲國｜已造訪狀態 1/256\n  戰爭：+1.0000\n"
              "國家：甲｜已造訪狀態 2/256\n  結盟：+2.0000\n")
    result = extract_country_experience(report, ("甲",))
    assert "結盟：+2.0000" in result
    assert "戰爭：+1.0000" not in result
    assert extract_country_experience(report, ("不存在",)) is None


def test_uploaded_q_report_can_be_separated():
    example = Path(__file__).resolve().parents[1] / 'upload' / 'rl_strategic_q_readable.txt'
    if not example.exists():
        return
    report = example.read_text(encoding='utf-8-sig')
    text = extract_country_experience(report, ('不朽傳奇',))
    assert text.startswith('國家：不朽傳奇｜')
    assert '國家：不死鳳凰｜' not in text
