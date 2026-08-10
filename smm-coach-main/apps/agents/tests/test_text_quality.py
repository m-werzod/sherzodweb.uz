from __future__ import annotations

from app.graphs.text_quality import is_substantive_answer, meaningful_word_count


def test_filler_answers_are_not_substantive() -> None:
    for junk in ("sen", "faqat sen borsan", "ok", "ha", "bilmayman", "", "   ", "sen sen sen"):
        assert not is_substantive_answer(junk), junk
        assert not is_substantive_answer(junk, min_words=4), junk


def test_real_answer_is_substantive() -> None:
    ans = (
        "Men 1 yildan ortiq e-commerce va marketplace loyihalarida ishlaganman, "
        "500 dollarga boshlangan proyekt hozir 16500 dollarga baholandi"
    )
    assert is_substantive_answer(ans)
    assert meaningful_word_count(ans) >= 12


def test_transcript_counts_only_user_answers() -> None:
    # AI questions (S:) must NOT inflate the count — only J: answers count.
    transcript = (
        "S: Bu mavzu bilan qanchadan beri shug'ullanasiz va qanday boshlagansiz?\n"
        "J: sen\n"
        "S: Aniq bitta misol keltiring, natija qanday bo'ldi va nega muhim edi?\n"
        "J: faqat sen borsan\n"
    )
    assert not is_substantive_answer(transcript)


def test_single_good_answer_passes_small_floor() -> None:
    assert is_substantive_answer(
        "marketpleysda sotuvni uch barobar oshirdim reklama orqali", min_words=4
    )


def test_multiline_answer_counts_continuation_lines() -> None:
    # A rich answer spanning several lines under ONE J: marker must count fully —
    # dropping continuation lines would flag a genuine interview as junk.
    transcript = (
        "S: Bu mavzu bilan tajribangizni ayting?\n"
        "J: Men uch yildan ortiq marketpleysda ishlayman\n"
        "birinchi oyda savdo juda past edi lekin reklama sozlagach\n"
        "har oyda daromad ikki barobar oshib bordi va endi jamoam bor\n"
    )
    assert is_substantive_answer(transcript)
    # The AI question line must still be excluded from the count.
    assert meaningful_word_count(transcript) >= 20
