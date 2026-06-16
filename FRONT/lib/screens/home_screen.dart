// Home: dashboard showing 4 farm tanks like a CCTV wall.
// Each tank represents an on-site camera. (Fixed 4 tanks — no add/remove)
// Tapping a tank does nothing in this build (no video feed).

import 'package:flutter/material.dart';

import '../tank_config.dart';
import 'photo_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Flatfish Doctor · Monitoring'),
        backgroundColor: const Color(0xFF0277BD),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: 'Analyze a photo',
            icon: const Icon(Icons.photo_camera),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const PhotoScreen()),
            ),
          ),
        ],
      ),
      body: GridView.count(
        padding: const EdgeInsets.all(12),
        crossAxisCount: 2,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: 0.92,
        children: [for (final t in kTanks) _tankCard(t)],
      ),
    );
  }

  Widget _tankCard(TankConfig tank) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.black45, width: 2),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // CCTV "screen" area — tank number
          Expanded(
            child: Stack(
              fit: StackFit.expand,
              children: [
                const ColoredBox(color: Color(0xFF101418)),
                Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('TANK',
                          style: TextStyle(
                              color: Colors.white60,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 1.5)),
                      Text(
                        tank.name.replaceAll(RegExp(r'[^0-9]'), ''),
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 44,
                            fontWeight: FontWeight.bold,
                            height: 1.0),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // status bar
          Container(
            width: double.infinity,
            color: Colors.white10,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: const Text(
              'Live feed',
              style: TextStyle(
                  color: Colors.white70,
                  fontWeight: FontWeight.w600,
                  fontSize: 13),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
