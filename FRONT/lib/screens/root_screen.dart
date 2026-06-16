// 하단 탭 컨테이너: [수조 모니터링] / [결과] 두 탭을 전환한다.

import 'package:flutter/material.dart';

import '../services/results_store.dart';
import 'home_screen.dart';
import 'results_screen.dart';

class RootScreen extends StatefulWidget {
  const RootScreen({super.key});

  @override
  State<RootScreen> createState() => _RootScreenState();
}

class _RootScreenState extends State<RootScreen> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    ResultsStore.instance.ensureLoaded();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [HomeScreen(), ResultsScreen()],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.grid_view), label: 'Monitoring'),
          NavigationDestination(icon: Icon(Icons.assignment), label: 'Results'),
        ],
      ),
    );
  }
}
