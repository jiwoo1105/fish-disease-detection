// 병(증상)별 대응 방안 — 하드코딩 가이드.
// 넙치(광어) 양식 현장 대응을 조사해 증상 코드별로 고정 수록한다.
// cls 증상 코드(white_spot/hemorrhage/...) 를 키로 사용한다. normal 은 가이드 없음.
// classes.yaml 의 매핑과 일관되며, 요약 화면에서 구체 조치를 보여주는 용도.

class DiseaseGuide {
  final String disease; // 대표 의심 질병
  final String tempAction; // 수온 관련 핵심 조치 (한 줄)
  final List<String> steps; // 단계별 대응
  final bool isolate; // 격리 권장 여부

  const DiseaseGuide({
    required this.disease,
    required this.tempAction,
    required this.steps,
    required this.isolate,
  });
}

const Map<String, DiseaseGuide> diseaseGuide = {
  'white_spot': DiseaseGuide(
    disease: '스쿠티카병 / 백점병',
    tempAction: '수온을 18℃ 이하로 낮추기 (고수온일수록 충 증식·폐사 증가)',
    steps: [
      '감염 개체 즉시 격리',
      '사육밀도 낮추고 환수량 늘리기',
      '포르말린·담수욕 등 약욕 처리 검토',
      '먹지 않은 사료·폐사체 즉시 제거',
    ],
    isolate: true,
  ),
  'hemorrhage': DiseaseGuide(
    disease: 'VHS·비브리오병·연쇄구균증',
    tempAction: 'VHS 의심 시 수온 20℃ 이상으로 상승 (저수온성 바이러스병)',
    steps: [
      '감염 수조 격리 및 사용 기구 소독',
      '세균성(비브리오·연쇄구균) 의심 시 항생제 투여 검토(수의 처방)',
      '암모니아·용존산소 등 수질 점검 및 개선',
      '폐사체 신속 제거로 2차 감염 차단',
    ],
    isolate: true,
  ),
  'color_change': DiseaseGuide(
    disease: '체색변화 (스트레스·초기 감염 신호)',
    tempAction: '수온 16~22℃ 정상 범위 유지',
    steps: [
      '수온·수질 급변 여부 점검',
      '개체 격리 후 출혈·궤양 등 추가 증상 관찰',
      '밀도·소음·광량 등 스트레스 요인 줄이기',
    ],
    isolate: false,
  ),
  'tumor': DiseaseGuide(
    disease: '림포시스티스병 (바이러스성 결절)',
    tempAction: '수온 정상 범위 유지 (특별한 수온 조치 불필요)',
    steps: [
      '전염성 낮음 — 대개 자연 치유',
      '스트레스 최소화 및 수질 관리에 집중',
      '결절이 커지거나 2차 감염 시 격리',
    ],
    isolate: false,
  ),
  'ulcer': DiseaseGuide(
    disease: '비브리오병 / 에드워드병 (궤양)',
    tempAction: '수온 25℃ 이상이면 즉시 낮추기 (세균 증식 가속)',
    steps: [
      '감염 개체 격리',
      '항생제 약욕·투여 검토 (수의 처방)',
      '수질 개선 및 사육밀도 감소',
      '상처 부위 2차 감염 방지',
    ],
    isolate: true,
  ),
  'emaciation': DiseaseGuide(
    disease: '여윔병',
    tempAction: '수온 정상 범위 유지',
    steps: [
      '사료 품질·급이량·급이 빈도 점검',
      '사육밀도 낮추기',
      '영양 강화 사료 급이',
      '기생충·내부 감염 여부 검사',
    ],
    isolate: false,
  ),
};
