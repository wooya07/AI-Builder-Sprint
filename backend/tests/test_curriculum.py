from app import document_parser, repository, service
from app.models import Course, TimetableRequest


def _course(code: str, section: str, day: str, start: int) -> Course:
    return Course(
        code=code,
        class_group_id=f"{code}-{section}",
        name=f"{code} 과목",
        credits=3,
        category="전공",
        instructor="테스트 교수",
        section=section,
        meetings=[{"day": day, "start": start, "end": start + 1}],
    )


def test_document_parser_uses_api_key_from_environment(monkeypatch):
    captured = {}

    class Response:
        ok = True

        def json(self):
            return {
                "elements": [{
                    "content": {
                        "html": "<table><tr><th>교과목번호</th><th>교과목명</th><th>학점</th></tr>"
                        "<tr><td>CS101</td><td>자료구조</td><td>3</td></tr></table>"
                    }
                }]
            }

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setenv("UPSTAGE_API_KEY", "up_environment_only")
    monkeypatch.setattr(document_parser.requests, "post", fake_post)
    result = document_parser.parse_curriculum_document(filename="curriculum.pdf", content=b"document")

    assert captured["headers"]["Authorization"] == "Bearer up_environment_only"
    assert result["course_count"] == 1
    assert result["courses"][0]["code"] == "CS101"


def test_document_parser_handles_merged_curriculum_headers_and_rows():
    parser = document_parser._TableHTMLParser()
    parser.feed("""
        <table>
          <tr><th rowspan="2">이수구분</th><th rowspan="2">교과목번호</th><th rowspan="2">교과목명(영문명)</th><th colspan="2">이수학기 및 학점</th><th rowspan="2">비고</th></tr>
          <tr><th>학점-이론-실습</th><th>학년-학기</th></tr>
          <tr><td rowspan="2">효원핵심교양</td><td>ZE1000113</td><td>대학영어(College English)</td><td>2-3-0</td><td>1-1</td><td></td></tr>
          <tr><td>ZE1000453</td><td>인공지능과디지털사고</td><td>3-3-0</td><td>1-1</td><td></td></tr>
          <tr><td colspan="3">소계</td><td>5</td><td></td><td></td></tr>
        </table>
    """)

    courses = document_parser._rows_to_courses([parser.rows])

    assert [(course["code"], course["name"]) for course in courses] == [
        ("ZE1000113", "대학영어(College English)"),
        ("ZE1000453", "인공지능과디지털사고"),
    ]
    assert courses[0]["category"] == "효원핵심교양"
    assert courses[1]["category"] == "효원핵심교양"
    assert courses[0]["credits"] == 2
    assert courses[0]["grade"] == "1"
    assert courses[0]["semester"] == "1"


def test_document_parser_exposes_upstage_table_debug_only_when_requested():
    payload = {"elements": [{"content": {"html": "<table><tr><td>교과목번호</td></tr><tr><td>CB1501009</td></tr></table>"}}]}

    tables, debug_tables = document_parser._extract_rows(payload, include_debug=True)

    assert tables == [[['교과목번호'], ['CB1501009']]]
    assert debug_tables == [{
        "element_index": 0,
        "source": "html",
        "raw_content": payload["elements"][0]["content"]["html"],
        "rows": tables[0],
    }]


def test_document_parser_prefers_detailed_course_category_column():
    courses = document_parser._rows_to_courses([[
        ["이수구분", "이수구분", "교과목번호", "교과목명", "학점", "학년-학기"],
        ["전공", "전공기초", "CB1501016", "논리회로및설계", "3", "2-1"],
    ]])

    assert courses[0]["category"] == "전공기초"
    assert courses[0]["code"] == "CB1501016"


def test_document_parser_skips_summary_and_merged_option_rows_and_normalises_codes():
    courses = document_parser._rows_to_courses([[
        ["교과목번호", "교과목명", "학점"],
        ["CB-150102 2", "컴퓨터구조", "3"],
        ["9 소계", "9 소계", "10"],
        ["ZFz000091 ZFz000092", "I. 사상과 역사 영역", "6"],
    ]])

    assert [(course["code"], course["name"]) for course in courses] == [
        ("CB1501022", "컴퓨터구조"),
    ]


def test_document_parser_distributes_codes_from_rowspan_continuation_table():
    courses = document_parser._rows_to_courses([[
        ["계", "계", "계", "계", "25", "", ""],
        ["전공", "전공기초", "CB150100 8 CB150100 9", "어드벤처디자인(Adventure Design)", "2-0-4", "1-2", ""],
        ["전공", "전공기초", "CB150100 8 CB150100 9", "일반물리학(II)(General Physics(II))", "3-3-0", "1-2", ""],
    ]])

    assert [(course["code"], course["name"], course["category"]) for course in courses] == [
        ("CB1501008", "어드벤처디자인(Adventure Design)", "전공기초"),
        ("CB1501009", "일반물리학(II)(General Physics(II))", "전공기초"),
    ]


def test_document_parser_splits_compact_multi_course_continuation_row():
    category = "\ud6a8\uc6d0\ud575\uc2ec\uad50\uc591"
    courses = document_parser._rows_to_courses([[
        [
            "\uad50\uc591", category,
            "ZE100011 3 ZE100045 3 ZE100009 1 CB100011 9",
            "\ub300\ud559\uc601\uc5b4(College English) "
            "\uc778\uacf5\uc9c0\ub2a5\uacfc\ub514\uc9c0\ud138\uc0ac\uace0(Artificial Intelligence and Digital Thinking) "
            "\uace0\uc804 \uc77d\uae30\uc640 \ud1a0\ub860 (Reading Classics of Great Literature) "
            "\uacf5\ud559\uc791\ubb38\ubc0f\ubc1c\ud45c(Technical Writing & Presentation)",
            "2-3-0 3-3-0 2-2-0 3-2-2",
            "1-1 1-1 1-2 3-2", "",
        ],
    ]])

    assert [(course["code"], course["credits"], course["grade"], course["semester"], course["category"])
            for course in courses] == [
        ("ZE1000113", 2, "1", "1", category),
        ("ZE1000453", 3, "1", "1", category),
        ("ZE1000091", 2, "1", "2", category),
        ("CB1000119", 3, "3", "2", category),
    ]
    assert [course["name"] for course in courses] == [
        "\ub300\ud559\uc601\uc5b4(College English)",
        "\uc778\uacf5\uc9c0\ub2a5\uacfc\ub514\uc9c0\ud138\uc0ac\uace0(Artificial Intelligence and Digital Thinking)",
        "\uace0\uc804 \uc77d\uae30\uc640 \ud1a0\ub860 (Reading Classics of Great Literature)",
        "\uacf5\ud559\uc791\ubb38\ubc0f\ubc1c\ud45c(Technical Writing & Presentation)",
    ]


def test_curriculum_matching_prefers_code_then_course_name(monkeypatch):
    catalog = [
        _course("CS101", "001", "월", 9),
        _course("CS102", "001", "화", 9),
    ]
    monkeypatch.setattr(repository, "list_courses", lambda: catalog)

    rows, codes = repository.match_curriculum_courses([
        {"code": "CS101", "name": "다른 이름"},
        {"code": None, "name": "CS102 과목"},
        {"code": "MISSING", "name": "없는 과목"},
    ])

    assert rows[0]["catalog_course_codes"] == []
    assert rows[0]["match_type"] is None
    assert rows[1]["catalog_course_codes"] == []
    assert rows[1]["match_type"] is None
    assert rows[2]["catalog_course_codes"] == []
    assert codes == []


def test_curriculum_matching_uses_code_prefix_and_name_then_exposes_catalog_code(monkeypatch):
    catalog = [_course("CB1501009", "001", "\uc6d4", 9).model_copy(update={"name": "General Physics II"})]
    monkeypatch.setattr(repository, "list_courses", lambda: catalog)

    rows, codes = repository.match_curriculum_courses([
        {"code": "CB1501999", "name": "General Physics II"},
    ])

    assert rows[0]["document_code"] == "CB1501999"
    assert rows[0]["code"] == "CB1501009"
    assert rows[0]["catalog_course_codes"] == ["CB1501009"]
    assert rows[0]["match_type"] == "prefix_name"
    assert codes == ["CB1501009"]


def test_curriculum_matching_does_not_match_same_name_from_another_department_prefix(monkeypatch):
    catalog = [_course("DM1500214", "001", "\uc6d4", 9).model_copy(update={"name": "General Physics I"})]
    monkeypatch.setattr(repository, "list_courses", lambda: catalog)

    rows, codes = repository.match_curriculum_courses([
        {"code": "CB1501005", "name": "General Physics I"},
    ])

    assert rows[0]["catalog_course_codes"] == []
    assert rows[0]["match_type"] is None
    assert codes == []


def test_curriculum_matching_ignores_parenthesized_english_translation(monkeypatch):
    catalog = [_course("PHYS101", "001", "월", 9).model_copy(update={"name": "일반물리학(II)"})]
    monkeypatch.setattr(repository, "list_courses", lambda: catalog)

    rows, codes = repository.match_curriculum_courses([
        {"code": None, "name": "일반물리학(II)(General Physics(II))"},
    ])

    assert rows[0]["catalog_course_codes"] == []
    assert rows[0]["match_type"] is None
    assert codes == []


def test_timetable_generation_limits_choices_to_curriculum_matches(monkeypatch):
    catalog = [
        _course("CS101", "001", "월", 9),
        _course("CS101", "002", "화", 9),
        _course("CS102", "001", "월", 10),
        _course("CS103", "001", "수", 9),
    ]
    monkeypatch.setattr(service, "list_courses", lambda: catalog)
    request = TimetableRequest(
        target_credits=6,
        candidate_course_codes=["CS101", "CS102", "CS103"],
        required_course_codes=["CS101"],
    )

    schedules = service.generate_timetables(request)

    assert schedules
    for schedule in schedules:
        codes = {course.code for course in schedule.courses}
        assert "CS101" in codes
        assert codes.issubset({"CS101", "CS102", "CS103"})
        assert len(codes) == len(schedule.courses)


def test_timetable_generation_returns_best_available_credits_when_exact_target_is_impossible(monkeypatch):
    catalog = [_course("CS101", "001", "\uc6d4", 13)]
    monkeypatch.setattr(service, "list_courses", lambda: catalog)

    schedules = service.generate_timetables(TimetableRequest(
        target_credits=12,
        candidate_course_codes=["CS101"],
    ))

    assert len(schedules) == 1
    assert schedules[0].total_credits == 3
    assert [course.code for course in schedules[0].courses] == ["CS101"]


def test_timetable_generation_diversifies_section_choices(monkeypatch):
    catalog = []
    for section, instructor in [("001", "Kim"), ("002", "Park"), ("003", "Lee")]:
        catalog.append(_course("STAT101", section, "월", 9).model_copy(update={"instructor": instructor}))
        catalog.append(_course("MATH101", section, "화", 9).model_copy(update={"instructor": instructor}))
    monkeypatch.setattr(service, "list_courses", lambda: catalog)

    schedules = service.generate_timetables(TimetableRequest(
        target_credits=6,
        candidate_course_codes=["STAT101", "MATH101"],
        max_results=3,
    ))

    statistics_instructors = {
        next(course.instructor for course in schedule.courses if course.code == "STAT101")
        for schedule in schedules
    }
    assert len(statistics_instructors) == 3
