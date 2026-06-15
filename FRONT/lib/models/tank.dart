// 수조(어항) 프로필과 모니터링 요약 데이터 모델.
// 홈 화면에서 수조를 등록/전환하고, 라이브 모니터링을 끝낼 때 만든 요약을
// 수조별로 저장한다. (shared_preferences 에 JSON 으로 직렬화)

/// 라이브 모니터링 1회 세션의 요약. (영상을 끌 때 생성)
class TankSummary {
  final int maxFish; // 세션 중 한 프레임에서 동시에 관측된 최대 넙치 수
  final int diseasedCount; // 그 중 이상 징후로 본 최대 마릿수
  final String riskLevel; // normal | watch | danger | immediate (세션 최악)
  final String? topSymptom; // 대표(최고 위험) 증상 코드
  final String? topDisease; // 대표 의심 질병명 (한글, classes.yaml 기준)
  final String? topAction; // 대표 권장 조치 코드
  final String temperature; // 권장 수온 안내 (없으면 '')
  final bool isolate; // 격리 권장 여부
  final DateTime time; // 요약 생성 시각

  const TankSummary({
    required this.maxFish,
    required this.diseasedCount,
    required this.riskLevel,
    required this.topSymptom,
    required this.topDisease,
    required this.topAction,
    required this.temperature,
    required this.isolate,
    required this.time,
  });

  Map<String, dynamic> toJson() => {
        'maxFish': maxFish,
        'diseasedCount': diseasedCount,
        'riskLevel': riskLevel,
        'topSymptom': topSymptom,
        'topDisease': topDisease,
        'topAction': topAction,
        'temperature': temperature,
        'isolate': isolate,
        'time': time.toIso8601String(),
      };

  factory TankSummary.fromJson(Map<String, dynamic> j) => TankSummary(
        maxFish: j['maxFish'] as int? ?? 0,
        diseasedCount: j['diseasedCount'] as int? ?? 0,
        riskLevel: j['riskLevel'] as String? ?? 'normal',
        topSymptom: j['topSymptom'] as String?,
        topDisease: j['topDisease'] as String?,
        topAction: j['topAction'] as String?,
        temperature: j['temperature'] as String? ?? '',
        isolate: j['isolate'] as bool? ?? false,
        time: DateTime.tryParse(j['time'] as String? ?? '') ?? DateTime(2000),
      );
}

/// 등록된 수조 1개.
class TankProfile {
  final String id;
  final String name;
  final TankSummary? lastSummary; // 마지막 모니터링 요약 (없으면 null)

  const TankProfile({
    required this.id,
    required this.name,
    this.lastSummary,
  });

  TankProfile copyWith({String? name, TankSummary? lastSummary}) => TankProfile(
        id: id,
        name: name ?? this.name,
        lastSummary: lastSummary ?? this.lastSummary,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'lastSummary': lastSummary?.toJson(),
      };

  factory TankProfile.fromJson(Map<String, dynamic> j) => TankProfile(
        id: j['id'] as String,
        name: j['name'] as String,
        lastSummary: j['lastSummary'] == null
            ? null
            : TankSummary.fromJson(
                (j['lastSummary'] as Map).cast<String, dynamic>()),
      );
}
