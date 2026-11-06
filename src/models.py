from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class Drug:
    """분석 대상 약 1개 (components 가 비면 성분 불명 = 판단 불가)."""

    label: str
    kind: str = "product"  # 'product' | 'ingredient'
    ingr_key: str = ""
    components: Tuple[str, ...] = ()  # 모든 키의 성분 합집합 (대체 표기 포함)
    alt_keys: Tuple[str, ...] = ()  # DUR 표기와 허가정보 표기가 다를 때의 '다른 쪽' 성분키
    map_source: str = ""
    entp: str = ""
    is_export: bool = False

    @property
    def resolved(self) -> bool:
        return bool(self.components)


@dataclass
class SearchHit:
    kind: str  # 'product' | 'ingredient'
    label: str  # 화면 표시용
    value: str  # product 는 ITEM_NAME, ingredient 는 영문 성분키
    resolved: bool = True


@dataclass
class Finding:
    kind: str  # 'dur' | 'dur_possible' | 'duplicate' | 'drugbank'
    severity: str  # 'contraindicated' | 'warning' | 'info'
    drug_a: str
    drug_b: str
    title: str
    reason: str = ""
    note: str = ""  # DUR 비고 (조건부 금기 문구)
    notice_no: str = ""
    apply_date: str = ""
    details: List[tuple] = field(default_factory=list)  # DrugBank: (성분A, 성분B, 설명, 별칭사용여부)


@dataclass
class Report:
    drugs: List[Drug]
    unresolved: List[Drug]
    findings: List[Finding]
    overall: str  # 'contraindicated' | 'warning' | 'caution' | 'none_found'
    overall_text: str
    ignored_duplicates: List[str] = field(default_factory=list)

    def of_kind(self, kind):
        return [f for f in self.findings if f.kind == kind]

    def count(self, kind):
        return len(self.of_kind(kind))
