// 모니터링 1회 세션의 누적 통계 → 종료 요약 생성.
// 실시간(live)과 영상 분석(video)이 공유한다.

import '../models/results.dart';
import '../models/tank.dart';

class SessionStats {
  int maxFish = 0; // 한 프레임에서 동시에 본 최대 넙치 수
  int maxDiseased = 0; // 그 중 이상 징후 최대 마릿수
  String worstLevel = 'normal'; // 세션 최악 위험 레벨
  FishResult? worstFish; // 대표(최고 위험) 개체

  static int _rank(String level) => switch (level) {
        'immediate' => 3,
        'danger' => 2,
        'watch' => 1,
        _ => 0,
      };

  /// 프레임 결과 1건을 누적 반영한다.
  void add(TankResult? r) {
    if (r == null) return;
    if (r.fishCount > maxFish) maxFish = r.fishCount;
    if (r.diseasedCount > maxDiseased) maxDiseased = r.diseasedCount;
    if (_rank(r.tankRiskLevel) > _rank(worstLevel)) worstLevel = r.tankRiskLevel;
    for (final f in r.alerts) {
      if (worstFish == null || f.riskScore > worstFish!.riskScore) {
        worstFish = f;
      }
    }
  }

  TankSummary build(DateTime time) {
    final w = worstFish;
    return TankSummary(
      maxFish: maxFish,
      diseasedCount: maxDiseased,
      riskLevel: worstLevel,
      topSymptom: w?.symptom,
      topDisease: w?.likelyDisease,
      topAction: w?.response?.action,
      temperature: w?.response?.temperature ?? '',
      isolate: w?.response?.isolate ?? false,
      time: time,
    );
  }
}
