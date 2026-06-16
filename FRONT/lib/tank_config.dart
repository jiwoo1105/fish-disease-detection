// 데모용 수조 설정 — 수조 4개. 각 수조에 지정 증상.
//   symptoms : 수조에 나타나는 증상 키 목록 (classes.yaml 기준)
//              (normal | hemorrhage | white_spot | tumor | color_change | emaciation | ulcer)
//
// 증상만 아래 목록에서 바꾸면 된다.

class TankConfig {
  final String id;
  final String name;
  final List<String> symptoms;

  const TankConfig({
    required this.id,
    required this.name,
    required this.symptoms,
  });
}

const kTanks = <TankConfig>[
  TankConfig(id: 'tank1', name: 'Tank 1', symptoms: ['hemorrhage']),
  TankConfig(id: 'tank2', name: 'Tank 2', symptoms: ['ulcer']),
  TankConfig(id: 'tank3', name: 'Tank 3', symptoms: ['tumor']),
  TankConfig(
      id: 'tank4', name: 'Tank 4', symptoms: ['hemorrhage', 'white_spot']),
];
