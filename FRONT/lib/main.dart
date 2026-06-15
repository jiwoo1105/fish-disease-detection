import 'package:flutter/material.dart';

import 'screens/home_screen.dart';

void main() {
  runApp(const NupchiDoctorApp());
}

class NupchiDoctorApp extends StatelessWidget {
  const NupchiDoctorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '넙치닥터',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF0277BD),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
